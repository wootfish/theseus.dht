from twisted.internet import reactor
from twisted.internet.defer import DeferredList
from twisted.logger import Logger
from twisted.protocols.policies import TimeoutMixin

from .enums import NodeInfoKeys, INITIATOR, CONNECTED
from .errors import Error201, Error202
from .krpc import KRPCProtocol


class DHTProtocol(KRPCProtocol, TimeoutMixin):
    log = Logger()

    idle_timeout = 34  # seconds
    peer_state = None
    local_peer = None

    supported_info_keys = set(key.value for key in NodeInfoKeys)

    _reactor = reactor

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # for generating responses to KRPC queries
        self.query_handlers.update({
            b'find': self.find,
            b'get': self.get,
            b'put': self.put,
            b'info': self.info,
            })

        # for processing data in responses to sent queries
        self.response_handlers.update({
            b'get': self.onGet,
            b'put': self.onPut,
            b'info': self.onInfo,
            })

    def connectionMade(self):
        super().connectionMade()
        self.setTimeout(self.idle_timeout)

        peer = self.transport.getPeer()
        peer_state = self.peer_state
        if peer_state:
            peer_state.state = CONNECTED
            peer_state.cnxn = self
            peer_state.host = peer.host

            if peer_state.role is INITIATOR:
                peer_state.getInfo()
        else:
            self.log.error("{peer} - connectionMade but peer_state is None -- this should never happen outside of unit tests", peer=(peer.host, peer.port))

    def connectionLost(self, reason):
        super().connectionLost(reason)
        self.setTimeout(None)

    def stringReceived(self, string):
        self.resetTimeout()
        KRPCProtocol.stringReceived(self, string)

    def find(self, args):
        pass  # TODO

    def get(self, args):
        pass  # TODO

    def info(self, args):
        info = args.get(b'info', {})
        keys = args.get(b'keys', [])

        # process remote info
        if type(info) is dict:
            if self.local_peer is not None:
                for key in info:
                    if key in self.supported_info_keys:
                        if self.local_peer.maybeUpdateInfo(self, key, info[key]):
                            self.log.debug("{peer} - Info update successful: {key}, {val}", peer=self._peer, key=key, val=info[key])
                        else:
                            self.log.debug("{peer} - Info update failed: {key}, {val}", peer=self._peer, key=key, val=info[key])
        else:
            self.log.debug("{peer} - Malformed query: Expected dict for value of 'info' key, not {type}", peer=self._peer, type=type(info))
            raise Error201("malformed 'info' argument")

        if type(keys) is list:
            d = self.getLocalKeys(keys)
            d.addCallback(lambda info: {"info": info})
            return d
        else:
            self.log.debug("{peer} - Malformed query: Expected list for value of 'keys' key, not {type}", peer=self._peer, type=type(keys))
            raise Error201("malformed 'keys' argument")

    def put(self, args):
        return args  # TODO

    def onGet(self, args):
        return args  # TODO

    def onInfo(self, args):
        return args  # TODO

    def onPut(self, args):
        return args  # TODO

    def getLocalKeys(self, keys=None):
        if keys is None:
            keys = self.supported_info_keys

        if all(key in self.supported_info_keys for key in keys):
            deferreds = []
            result = {}
            for key in keys:
                def callback(value):
                    result[key] = value

                d = self.local_peer.getInfo(key)
                d.addCallback(callback)
                deferreds.append(d)
            deferred_list = DeferredList(deferreds)
            deferred_list.addCallback(lambda _: result)
            return deferred_list
        else:
            self.log.debug("{peer} - Unrecognized info key(s) requested. Requested keys: {keys}", peer=self._peer, keys=keys)
            raise Error202("info key not supported")
