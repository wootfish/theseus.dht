from twisted.logger import Logger
from twisted.protocols.policies import TimeoutMixin

from .krpc import KRPCProtocol
from .enums import NodeInfoKeys


class DHTProtocol(KRPCProtocol, TimeoutMixin):
    log = Logger()
    idle_timeout = 34  # seconds

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

    # the dispatcher populates the protocol's find, onFind, get, put, onGet,
    # info, and onInfo callbacks during buildProtocol

    def connectionMade(self):
        super().connectionMade()

        self.log.info("Encrypted channel established with {addr}", addr=self.transport.getPeer())
        self.setTimeout(self.idle_timeout)

    def connectionLost(self, reason):
        super().connectionLost(reason)

        self.setTimeout(None)

    def timeoutConnection(self):  # called by TimeoutMixin
        self.log.info("Connection to {addr} timed out after {n} seconds",
                      addr=self.transport.getPeer(), n=self.idle_timeout)
        self.transport.loseConnection()

    def stringReceived(self, string):
        self.resetTimeout()
        super().stringReceived(string)

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
