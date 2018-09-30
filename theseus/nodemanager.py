from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.logger import Logger

from .constants import timeout_window
from .nodeaddr import NodeAddress


class NodeManager:
    """
    Responsible for managing local nodes:
    - generating & cycling thru node addrs
    - creating & maintaining data stores
    - proxying inserts or queries to data stores
    """

    log = Logger()
    callLater = reactor.callLater

    def __init__(self, num_nodes):
        self.node_addrs = []
        self.backlog = []
        self.listeners = []
        self.num_nodes = num_nodes

    def start(self, local_ip='127.0.0.1'):
        for _ in range(self.num_nodes):
            self.add_addr(local_ip)

    def get_addrs(self):
        if len(self.node_addrs) == self.num_nodes:
            return self.node_addrs
        d = Deferred()
        self.backlog.append(d)
        return d

    def add_listener(self, listener):
        self.listeners.append(listener)

    @inlineCallbacks
    def add_addr(self, local_ip):
        result = yield NodeAddress.new(local_ip)
        self.node_addrs.append(result)
        # TODO create a data store for this addr
        self.callLater(max(timeout_window - 5, 0), self.addr_timeout, result)

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

    def addr_timeout(self, node_address):
        self.node_addrs.remove(node_address)
        # TODO remove data store for this addr
        self.add_addr()
