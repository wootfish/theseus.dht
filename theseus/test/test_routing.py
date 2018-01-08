from twisted.trial import unittest
from twisted.internet.address import IPv4Address

from theseus.nodeid import NodeID
from theseus.routing import RoutingTable
from theseus.nodemanager import NodeManagerService

from theseus.test import test_node


class SingleNodeRoutingTableTests(unittest.TestCase):
    def setUp(self):
        test_node.NodeTests.setUp(self)  # apply NodeService testing harness

        self.node_manager = NodeManagerService(num_nodes=1)
        self.node_manager.startService()

        self.table = RoutingTable(self.node_manager)

    def tearDown(self):
        test_node.NodeTests.tearDown(self)  # remove NodeService harness

    def test_insert(self):
        self.assertTrue(self.table.insert(
                IPv4Address("TCP", "127.0.0.1", 2048),
                NodeID(b'\x00' * 20, verify=False)
                ))
        self.assertTrue(self.table.insert(
                IPv4Address("TCP", "127.0.0.1", 2049),
                NodeID(b'\x01' * 20, verify=False)
                ))
        self.assertTrue(self.table.insert(
                IPv4Address("TCP", "127.0.0.1", 2050),
                NodeID(b'\x02' * 20, verify=False)
                ))

        self.assertIn(IPv4Address("TCP", "127.0.0.1", 2048), self.table)
        self.assertIn(IPv4Address("TCP", "127.0.0.1", 2049), self.table)
        self.assertIn(IPv4Address("TCP", "127.0.0.1", 2050), self.table)

    def test_remove(self):
        self.test_insert()

        self.assertTrue(self.table.remove(IPv4Address("TCP", "127.0.0.1", 2049)))

        self.assertIn(IPv4Address("TCP", "127.0.0.1", 2048), self.table)
        self.assertNotIn(IPv4Address("TCP", "127.0.0.1", 2049), self.table)
        self.assertIn(IPv4Address("TCP", "127.0.0.1", 2050), self.table)

class MultiNodeRoutingTableTests(unittest.TestCase):
    def setUp(self):
        test_node.NodeTests.setUp(self)  # apply NodeService testing harness

        self.node_manager = theseus.nodemanager.NodeManagerService()
        self.node_manager.startService()

        self.table = theseus.routing.RoutingTable(self.node_manager)

    def tearDown(self):
        test_node.NodeTests.tearDown(self)  # remove NodeService harness
