from twisted.application.service import MultiService
from twisted.logger import Logger

from .node import NodeService


class NodeManagerService(MultiService):
    log = Logger()
    num_nodes = 5

    def __init__(self, num_nodes=None):
        super().__init__()

        if num_nodes is not None:
            self.num_nodes = num_nodes

        for _ in range(self.num_nodes):
            self.addService(NodeService(self))
