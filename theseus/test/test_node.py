from twisted.trial import unittest
from twisted.internet.error import CannotListenError

from theseus.node import NodeService
from theseus.nodemanager import NodeManagerService

import random
import collections


class NodeTests(unittest.TestCase):
    listen_port_range = [1337, 42000]
    seed = 17

    def setUp(self):
        def dumb_dummy(*args, **kwargs):
            raise NotImplementedError

        self.test_rng = random.Random(x=NodeTests.seed)
        self.mirror_rng = random.Random(x=NodeTests.seed)

        self.old_randrange = NodeService._randrange
        self.old_updateID = NodeService.updateID

        NodeService._randrange = self.test_rng.randrange
        NodeService.updateID = dumb_dummy

    def tearDown(self):
        NodeService._randrange = self.old_randrange
        NodeService.updateID = self.old_updateID

    def test_listening(self):
        # test-specific setup
        node_data = collections.defaultdict(dict)

        def new_update_ID(self):
            node_data[self]["update_id_called"] = True

        def new_listen(self, port):
            if "port" in node_data[self]:
                raise Exception("node tried to start listening more than once")
            node_data[self]["port"] = port

        self.old_listen = NodeService._listen
        NodeService._listen = new_listen
        NodeService.updateID = new_update_ID

        # test proper
        node_manager = NodeManagerService()
        node_manager.startService()

        for node in node_manager:
            self.assertIn(node, node_data)
            self.assertTrue(node_data[node]["update_id_called"])
            self.assertEqual(node_data[node]["port"], node.listen_port)
            self.assertEqual(node.listen_port, self.mirror_rng.randrange(*self.listen_port_range))

        # test-specific teardown
        NodeService._listen = self.old_listen
