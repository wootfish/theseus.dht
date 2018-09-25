from twisted.internet import reactor
from twisted.internet.defer import DeferredList, inlineCallbacks
from twisted.logger import Logger
from twisted.protocols.policies import TimeoutMixin

from .enums import DHTInfoKeys, INITIATOR, CONNECTED
from .errors import Error201, Error202, UnsupportedInfoError
from .krpc import KRPCProtocol


class DHTProtocol(KRPCProtocol, TimeoutMixin):
    log = Logger()

    idle_timeout = 34  # seconds
    peer_state = None
    local_peer = None

    supported_info_keys = set(key.value for key in DHTInfoKeys)

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
        pass  # TODO

    def get(self, args):
        pass  # TODO

    def info(self, args):
        info = args.get(b'info', {})
        keys = args.get(b'keys', [])

        # process remote info
        if type(info) is dict:
            if self.local_peer is not None:
                for key, val in info.items():
                    result = "Successful" if self.local_peer.maybe_update_info(self, key, val) else "Failed"
                    self.log.debug("{peer} - {result} info update: {key}, {val}", peer=self._peer, result=result, key=key, val=val)
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
        return args  # TODO

    def onGet(self, args):
        return args  # TODO

    def onInfo(self, args):
        ...
        return args  # has to return args to support anything further down on the Deferred callback chain

    def onPut(self, args):
        return args  # TODO

    @inlineCallbacks
    def get_local_keys(self, keys=None):
        if keys is None:
            keys = self.supported_info_keys
        else:
            keys = [key if type(key) is bytes else key.value for key in keys]

        self.log.debug("{peer} - Getting local keys {keys}", peer=self._peer, keys=keys)
        result = {}
        try:
            for key in keys:
                if self.local_peer is None:
                    raise UnsupportedInfoError()  # no info supported if local_peer is None
                result[key] = yield self.local_peer.get_info(key)
        except UnsupportedInfoError:
            self.log.debug("{peer} - Unsupported info key {key} requested.", peer=self._peer, key=key)
            raise Error202("info key not supported")
        return result
