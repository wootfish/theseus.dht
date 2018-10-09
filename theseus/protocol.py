from twisted.internet import reactor
from twisted.internet.defer import DeferredList, inlineCallbacks
from twisted.logger import Logger
from twisted.protocols.policies import TimeoutMixin

from .constants import L
from .enums import DHTInfoKeys, INITIATOR, CONNECTED
from .errors import Error201, Error202
from .krpc import KRPCProtocol

from socket import inet_aton


class DHTProtocol(KRPCProtocol, TimeoutMixin):
    log = Logger()

    idle_timeout = 34  # seconds
    peer_state = None
    local_peer = None

    supported_info_keys = set(key.value for key in DHTInfoKeys)

    _reactor = reactor

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # for generating responses to received queries
        self.query_handlers.update({
            b'find': self.find,
            b'get': self.get,
            b'put': self.put,
            b'info': self.info,
            })

        # for processing data in responses to sent queries
        self.response_handlers.update({
            b'info': self.onInfo,
            })

    def connectionMade(self):
        super().connectionMade()
        self.setTimeout(self.idle_timeout)

        if self.peer_state:
            self.peer_state.on_connect(self)
        else:
            peer = self.transport.getPeer()
            self.log.error("{peer} - connectionMade but peer_state is None -- this should have been populated by the factory", peer=(peer.host, peer.port))

    def connectionLost(self, reason):
        super().connectionLost(reason)
        self.setTimeout(None)

    def stringReceived(self, string):
        self.resetTimeout()
        KRPCProtocol.stringReceived(self, string)

    def timeoutConnection(self):
        self.log.debug("Connection to {peer} timed out after {s} seconds.", peer=self._peer, s=self.idle_timeout)
        super().timeoutConnection()

    def find(self, args):
        addr = args.get(b'addr')
        if addr is None:
            raise Error201("missing 'addr' argument")
        if self.local_peer is None:
            return {"nodes": []}
        return {"nodes": [entry.as_bytes() for entry in self.local_peer.routing_table.query(addr)]}

    def get(self, args):
        addr = args.get(b'addr')
        tag_names = args.get(b'tags', [])

        if addr is not None:
            if type(addr) is not bytes or len(addr) != L//8:
                raise Error201('valid addr required')
        if type(tag_names) is not list or not all(type(name) is bytes for name in tag_names):
            raise Error201('tags must be list of bytestrings')

        data = self.local_peer.node_manager.get(addr, tag_names)

        if len(data) == 0:
            # no data, so return routing info instead
            # TODO is this even a good idea? MLDHT does it but that doesn't necessarily mean it's smart
            # in particular it doesn't accomodate our generalizations well (see FIXME below)
            if addr is None:
                raise Exception("can't return routing info for addr=None")  # FIXME this edge case is an oversight in the spec
            return self.find({b'addr': addr})

        return {'data': data}

    def info(self, args):
        info = args.get(b'info', {})
        keys = args.get(b'keys', [])

        # process remote info
        if type(info) is dict:
            self.on_advertise(info)
        else:
            self.log.debug("{peer} - Malformed query: Expected dict for value of 'info' key, not {t}", peer=self._peer, t=type(info))
            raise Error201("malformed 'info' argument")

        if type(keys) is list:
            d = self.get_local_keys(keys)
            d.addCallback(lambda info: {"info": info})
            return d
        else:
            self.log.debug("{peer} - Malformed query: Expected list for value of 'keys' key, not {type}", peer=self._peer, type=type(keys))
            raise Error201("malformed 'keys' argument")

    def put(self, args):
        # TODO look for sybil arg, respond
        suggested_duration = args.get(b't')
        addr = args.get(b'addr')
        data = args.get(b'data')
        tag_names = args.get(b'tags', [])

        if suggested_duration is not None and type(suggested_duration) is not int:
            raise Error201('t must be int')
        if type(addr) is not bytes or len(addr) != L//8:
            raise Error201('addr must be {} bytes'.format(L//8))
        if type(data) is not bytes:
            raise Error201('data must be bytes')
        if type(tag_names) is not list or not all(type(name) is bytes for name in tag_names):
            raise Error201('tags must be list of bytestrings')

        tags = self.get_tags(tag_names)
        if suggested_duration is None:
            duration = self.local_peer.node_manager.put(addr, data, tags)
        else:
            duration = self.local_peer.node_manager.put(addr, data, tags, suggested_duration)

        return {"d": duration} if len(tags) == 0 else {"d": duration, "tags": tags}

    def onInfo(self, args):
        info = args.get(b'info')
        if type(info) is dict:
            self.on_advertise(info)
        else:
            self.log.debug("{peer} - Malformed response: Expected dict for value of 'info' key, not {t}", peer=self._peer, t=type(info))
        return args  # has to return args to support anything further down on the Deferred callback chain

    @inlineCallbacks
    def get_local_keys(self, keys=None):
        if keys is None:
            keys = self.supported_info_keys
        else:
            keys = [key if type(key) is bytes else key.value for key in keys]

        self.log.debug("{peer} - Getting local keys {keys}", peer=self._peer, keys=keys)
        result = {}

        for key in keys:
            if self.local_peer is None:  # no info available if local_peer is None
                self.log.debug("{peer} - Unsupported info key {key} requested.", peer=self._peer, key=key)
                raise Error202("info key not supported")
            result[key] = yield self.local_peer.get_info(key)

        self.log.debug("{peer} - Keys: {keys}", peer=self._peer, keys=result)
        return result

    def get_tags(self, tag_names):
        tags = {}
        for name in tag_names:
            if name == b'ip':
                tags[name] = inet_aton(self.transport.getPeer().host)
            elif name == b'port':
                port = self.transport.getPeer().port
                tags[name] = bytes([port >> 8, port & 0xFF])
            else:
                tags[name] = b''
        return tags

    def on_advertise(self, info):
        if self.local_peer is not None:
            for key, val in info.items():
                result = "Successful" if self.local_peer.maybe_update_info(self, key, val) else "Failed"
                self.log.debug("{peer} - {result} info update: {key}, {val}", peer=self._peer, result=result, key=key, val=val)
