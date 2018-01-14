from twisted.application.service import MultiService
from twisted.logger import Logger

from .node import NodeService
from .routing import RoutingTable
from .datastore import DataStore


class NodeManagerService(MultiService):
    log = Logger()
    num_nodes = 5

    def __init__(self, num_nodes=None, node_ids=None):
        super().__init__()

        self.table = RoutingTable(self)
        self.data_store = DataStore()

        if num_nodes is not None:
            self.num_nodes = num_nodes
        elif node_ids is not None:
            self.num_nodes = len(node_ids)

        if node_ids is None:
            for _ in range(self.num_nodes):
                self.addService(NodeService(self))
        else:
            if num_nodes is not None and len(node_ids) != num_nodes:
                raise Exception("len(node_ids) and num_nodes disagree")

            for node_id in node_ids:
                self.addService(NodeService(self, node_id))
