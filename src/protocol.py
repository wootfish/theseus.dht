from twisted.protocols.policies import TimeoutMixin
from twisted.logger import Logger

from .krpc import KRPCProtocol

from collections import OrderedDict


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
            b'find': self.onFind,
            b'get': self.onGet,
            b'put': self.onPut,
            b'info': self.onInfo,
            })

        # info_updaters needs to be OrderedDict because it gets iterated over
        #self.info_updaters = OrderedDict((
        #    (b'listen_port', self.iListenPort),
        #    (b'id', self.iId),
        #    ))

    def connectionMade(self):
        self.setTimeout(self.idle_timeout)

    def connectionLost(self, reason):
        super().connectionLost(reason)

        self.setTimeout(None)

    def timeoutConnection(self):  # called by TimeoutMixin
        self.log.info("Connection to {state} timed out after {n} seconds",
                      state=self.remote_state, n=self.idle_timeout)
        self.transport.loseConnection()

    def stringReceived(self, string):
        super().stringReceived(string)

        self.resetTimeout()

    def onQuery(self, txn_id, query_name, args):
        self.log.info("Query from {node} (txn {txn}): {name} {args}",
                      node=self.remote_state, name=query_name, txn=txn_id, args=args)

    # find and onFind callbacks are populated from the routing table
    # get, put, and onGet callbacks are populated from the data store
    # info and onInfo callbacks are populated by the dispatcher
