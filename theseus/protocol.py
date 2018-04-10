from twisted.logger import Logger
from twisted.internet.defer import Deferred, DeferredList
from twisted.protocols.policies import TimeoutMixin

from .krpc import KRPCProtocol
from .enums import NodeInfoKeys


class DHTProtocol(KRPCProtocol, TimeoutMixin):
    log = Logger()
    idle_timeout = 34  # seconds
    node_state = None
    local_peer = None

    default_info = [key.value for key in NodeInfoKeys]

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
            #b'find': self.onFind,
            b'get': self.onGet,
            b'put': self.onPut,
            b'info': self.onInfo,
            })

    def connectionMade(self):
        super().connectionMade()
        self.setTimeout(self.idle_timeout)

        peer = self.transport.getPeer()
        self.node_state.host = peer.host
        self.node_state.getInfo(self.default_info, advertise={
            key: self.local_peer.getInfo(key) for key in self.default_info
            })

    def connectionLost(self, reason):
        super().connectionLost(reason)
        self.setTimeout(None)

    def stringReceived(self, string):
        self.resetTimeout()
        KRPCProtocol.stringReceived(string)

    def onQuery(self, txn_id, query_name, args):
        self.log.info("Query from {addr} (txn {txn}): {name} {args}",
                      addr=self.transport.getPeer(), name=query_name, txn=txn_id, args=args)

    def find(self, args):
        pass  # TODO: fill out after making real data store

    def get(self, args):
        pass  # TODO

    def info(self, args):
        supported_keys = set(key.value for key in NodeInfoKeys)
        info = args.get(b'info', {})
        keys = args.get(b'keys', [])
        local_info = {}

        # process remote info
        if type(info) is dict:
            if self.local_peer is not None:
                for key in info:
                    self.local_peer.maybeUpdateInfo(self, key, info[key])
        else:
            self.log.debug("Malformed query: Expected dict for value of 'info' key, not {type}", type=type(info))
            return "malformed 'info' value"

        # collect values for requested info keys
        if type(keys) is list:
            if supported_keys >= set(type(value) for value in keys):
                for key in keys:
                    local_info[key] = self.local_peer.getInfo(key)    # TODO patch getInfo to provide Deferreds for pending results, and patch this to properly handle those
                deferred_list = DeferredList([d for d in local_info.values() if type(d) is Deferred])
                deferred_list.addCallback(lambda _: {"info": {
                    key: (value.result if type(value) is Deferred else value)
                    for key, value in local_info.items()
                    }})
                return deferred_list
            else:
                self.log.debug("Unrecognized info key(s) requested. Requested keys: {keys}", keys=keys)
                return "info key not supported"
        else:
            self.log.debug("Malformed query: Expected list for value of 'keys' key, not {type}", type=type(keys))
            return "malformed 'keys' value"

    def put(self, args):
        pass  # TODO

    def onGet(self, args):
        pass  # TODO

    def onInfo(self, args):
        pass  # TODO

    def onPut(self, args):
        pass  # TODO
