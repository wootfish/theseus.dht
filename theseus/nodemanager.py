from twisted.internet import reactor
from twisted.internet.task import LoopingCall
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

    _clock = reactor

    def __init__(self, num_nodes, local_ip='127.0.0.1'):
        self.running = False
        self.num_nodes = num_nodes
        self.local_ip = local_ip

        self.looping_calls = [None] * num_nodes
        self.data_stores = [None] * num_nodes
        self.node_addrs = [None] * num_nodes

        self.backlog = []
        self.listeners = []

    def start(self):
        self.running = True

        for index in range(self.num_nodes):
            lc = LoopingCall(self.populate_addr, index)
            lc.clock = self._clock
            lc.start(timeout_window)
            self.looping_calls[index] = lc

    def stop(self):
        self.running = False

        # halt the LoopingCalls
        for call in self.looping_calls:
            if call is not None and call.running:
                call.stop()

    def get_addrs(self):
        if None in self.node_addrs:
            d = Deferred()
            self.backlog.append(d)
            return d
        return self.node_addrs

    def add_listener(self, listener):
        self.listeners.append(listener)

    @inlineCallbacks
    def populate_addr(self, index):
        try:
            self.node_addrs[index] = None
            result = yield NodeAddress.new(self.local_ip)
            if not self.running:  # if the NodeManager was stopped while we were waiting on this NodeAddress
                return
            self.node_addrs[index] = result
            store = DataStore(result.addr)
            self.data_stores[index] = store

            self.log.debug("New node addr added. Current node addrs: {a}", a=', '.join("None" if node_addr is None else node_addr.addr.hex() for node_addr in self.node_addrs))

            if None not in self.node_addrs:
                self.log.info("All local node addresses generated.")
                tup = tuple(self.node_addrs)

                for listener in self.listeners:
                    try:
                        listener(tup)
                    except Exception as e:
                        self.log.failure("Error in NodeManager listener callback")
                while self.backlog:
                    self.backlog.pop().callback(self.node_addrs)

        except Exception:
            self.log.failure("unexpected exception while adding address")

    def put(self, addr, datum, tags=None, suggested_duration=None):
        store = min(self.data_stores, key=lambda store: float('inf') if store is None else store._get_distance(addr))
        if store is None:
            self.log.warn("Tried to put data without any local data stores!")
            return 0
        return store.put(addr, datum, tags or {}, suggested_duration)

    def get(self, addr, tag_names=None):
        if all(store is None for store in self.data_stores):
            self.log.warn("Tried to get data without any local data stores!")
            return 0

        data = set()
        args = (addr,) if tag_names is None else (addr, tag_names)
        for store in self.data_stores:
            if store is not None:
                data.update(store.get(*args))
        return list(data)
