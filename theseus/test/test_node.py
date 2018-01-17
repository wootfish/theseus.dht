from twisted.trial import unittest
from twisted.internet.error import CannotListenError

import theseus.node
import theseus.nodemanager

import random
import collections


# TODO figure out how to fuck with config directly rather than just copying
# over relevant parameters

class NodeTests(unittest.TestCase):
    listen_port_range = [1337, 42000]
    seed = 17

    def setUp(self):
        def dumb_dummy(*args, **kwargs):
            raise NotImplementedError

        self.test_rng = random.Random(x=NodeTests.seed)
        self.mirror_rng = random.Random(x=NodeTests.seed)

        # functions to swap out: node.randrange, NodeService._listen, NodeService.updateID

        self._old_randrange = theseus.node.randrange
        theseus.node.randrange = self.test_rng.randrange

        NodeService = theseus.node.NodeService

        self._old_updateid = NodeService.updateID
        self._old_listen = NodeService._listen

        NodeService.updateID = dumb_dummy
        NodeService._listen = dumb_dummy

    def tearDown(self):
        theseus.node.randrange = self._old_randrange
        theseus.node.NodeService.updateID = self._old_updateid
        theseus.node.NodeService._listen = self._old_listen

    def test_listening(self):
        node_data = collections.defaultdict(dict)

        def new_update_ID(self):
            node_data[self]["update_id_called"] = True

        def new_listen(self, port):
            if "port" in node_data[self]:
                raise Exception("node tried to listen while already listening")
            node_data[self]["port"] = port

        NodeService = theseus.node.NodeService
        NodeService.updateID = new_update_ID
        NodeService._listen = new_listen

        node_manager = theseus.nodemanager.NodeManagerService()
        node_manager.startService()

        for node in node_manager:
            self.assertIn(node, node_data)
            self.assertTrue(node_data[node]["update_id_called"])
            self.assertEqual(node_data[node]["port"], node.listen_port)
            self.assertEqual(node.listen_port, self.mirror_rng.randrange(*self.listen_port_range))
