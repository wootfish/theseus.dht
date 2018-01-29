from twisted.protocols.policies import TimeoutMixin
from twisted.logger import Logger

from .krpc import KRPCProtocol
from .enums import NodeInfoKeys


class DHTProtocol(KRPCProtocol, TimeoutMixin):
    log = Logger()

    idle_timeout = 34  # seconds

    # the info_updaters and info_getters callbacks are populated by the factory
    # during buildProtocol
    info_updaters = None
    info_getters = None

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

        self.setTimeout(self.idle_timeout)

    def connectionLost(self, reason):
        super().connectionLost(reason)

        self.setTimeout(None)

    def timeoutConnection(self):  # called by TimeoutMixin
        self.log.info("Connection to {addr} timed out after {n} seconds",
                      addr=self.transport.getPeer(), n=self.idle_timeout)
        self.transport.loseConnection()

    def stringReceived(self, string):
        super().stringReceived(string)

        self.resetTimeout()

    def onQuery(self, txn_id, query_name, args):
        self.log.info("Query from {node} (txn {txn}): {name} {args}",
                      node=self.remote_state, name=query_name, txn=txn_id, args=args)

    def get(self, args):
        # data = self.maybeGet(args)
        # if data is None:
        #     return self.find(args)
        # return {"data": data}

        pass  # TODO: fill out after making real data store

    def onGet(self, args):
        pass  # TODO: fill out at the same time as self.get

    def put(self, args):
        pass  # TODO: fill out at the same time as self.get

    def onPut(self, args):
        pass  # TODO: fill out at the same time as self.get

    def info(self, args):
        self.onInfo(args)  # update any advertised info keys

        info = {}
        requested = args.get(b'keys', [])
        for key in NodeInfoKeys:
            if key.value in requested:
                info[key.value] = self.info_getters[key]()

        return {b'info': info}

    def onInfo(self, args):
        info = args.get(b'info', {})

        for key in NodeInfoKeys:
            if key.value in info:
                self.info_setters[key](self, info[key.value])

    def find(self, args):
        target_addr = args.get(b'addr')
        if type(target_addr) is not bytes or len(target_addr) != 20:
            raise Exception("bad find addr")
        return {"nodes": self.routing_query(target_addr)}
