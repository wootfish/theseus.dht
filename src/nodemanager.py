from twisted.application.service import MultiService

from .node import NodeService


class NodeManagerService(MultiService):
    log = Logger()
    num_nodes = 5

    def __init__(self):
        for _ in self.num_nodes:
            self.addService(NodeService(self))
