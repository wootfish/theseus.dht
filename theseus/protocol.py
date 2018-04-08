from twisted.logger import Logger
from twisted.protocols.policies import TimeoutMixin

from .krpc import KRPCProtocol


class DHTProtocol(KRPCProtocol, TimeoutMixin):
    log = Logger()
    idle_timeout = 34  # seconds
    node_state = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.query_handlers.update({
            b'find': self.find,
            b'get': self.get,
            b'put': self.put,
            b'info': self.info,
            })

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
        if self.node_state is not None:
            self.node_state.host = peer.host

        #self.log.info("Connection made with {addr}", addr=peer)

    def connectionLost(self, reason):
        super().connectionLost(reason)
        self.setTimeout(None)

        #self.log.info("Connection lost with {addr}", addr=self.node_state.host)

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
        pass  # TODO

    def put(self, args):
        pass  # TODO

    def onGet(self, args):
        pass  # TODO

    def onInfo(self, args):
        pass  # TODO

    def onPut(self, args):
        pass  # TODO
