from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, Deferred, succeed
from twisted.logger import Logger

from .constants import timeout_window
from .nodeaddr import NodeAddress
from .datastore import DataStore


class NodeManager:
    """
    Responsible for managing local nodes:
    - generating & cycling thru node addrs
    - creating & maintaining data stores
    - proxying inserts or queries to data stores
    """
    # TODO local_ip should probably not be hardcoded in start and addr_timeout -- figure out something better

    log = Logger()
    callLater = reactor.callLater

    def __init__(self, num_nodes):
        self.data_stores = []
        self.node_addrs = []
        self.backlog = []
        self.listeners = []
        self.num_nodes = num_nodes

    def start(self, local_ip='127.0.0.1'):
        for _ in range(self.num_nodes):
            self.add_addr(local_ip)

    def get_addrs(self):
        if len(self.node_addrs) == self.num_nodes:
            return succeed(self.node_addrs)
        d = Deferred()
        self.backlog.append(d)
        return d

    def add_listener(self, listener):
        self.listeners.append(listener)

    @inlineCallbacks
    def add_addr(self, local_ip):
        try:
            result = yield NodeAddress.new(local_ip)
            store = DataStore(result)

            self.node_addrs.append(result)
            self.data_stores.append(store)
            self.callLater(max(timeout_window - 5, 0), self.addr_timeout, result, store)
            self.log.debug("New node addr added. Current {n} node addrs: {addrs}", n=len(self.node_addrs), addrs=self.node_addrs)

            if len(self.node_addrs) == self.num_nodes:
                self.log.info("All local node addresses generated.")
                for listener in self.listeners:
                    try:
                        listener(self.node_addrs)
                    except Exception as e:
                        self.log.failure("Error in NodeManager listener callback")
                while self.backlog:
                    self.backlog.pop().callback(self.node_addrs)

        except Exception:
            self.log.failure("unexpected exception while adding address")

    def addr_timeout(self, node_address, data_store, local_ip='127.0.0.1'):
        self.node_addrs.remove(node_address)
        self.data_stores.remove(data_store)
        self.add_addr(local_ip)

    def put(self, addr, datum, tags=None, suggested_duration=float('inf')):
        if len(self.data_stores) == 0:
            return 0
        store = min(self.data_stores, key=lambda store: store._get_distance(addr))
        return store.put(addr, datum, tags or {}, suggested_duration)
