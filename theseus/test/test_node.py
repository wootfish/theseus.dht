from twisted.trial import unittest
from twisted.internet.error import CannotListenError

import theseus.node
import theseus.nodemanager

import random


# TODO figure out how to fuck with config directly rather than just copying
# over relevant parameters

class NodeTests(unittest.TestCase):
    listen_port_range = [1337, 42000]
    seed = 17

    def setUp(self):
        self.test_rng = random.Random(x=self.seed)
        self.mirror_rng = random.Random(x=self.seed)

        # functions to swap out: node.randrange, NodeService._listen, NodeService.updateID

        self._old_randrange = theseus.node.randrange
        theseus.node.randrange = self.test_rng.randrange

        NodeService = theseus.node.NodeService

        self._old_updateid = NodeService.updateID
        self._old_listen = NodeService._listen
        NodeService.updateID = lambda self: None
        NodeService._listen = lambda self, port: None

    def tearDown(self):
        theseus.node.randrange = self._old_randrange
        theseus.node.NodeService.updateID = self._old_updateid
        theseus.node.NodeService._listen = self._old_listen

    def test_listening(self):
        node_manager = theseus.nodemanager.NodeManagerService()
        node_manager.startService()

        for node in node_manager:
            self.assertEqual(node.listen_port, self.mirror_rng.randrange(*self.listen_port_range))
