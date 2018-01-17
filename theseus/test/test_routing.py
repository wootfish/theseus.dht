from twisted.trial import unittest
from twisted.internet.address import IPv4Address

from theseus.nodeid import NodeID
from theseus.routing import RoutingTable
from theseus.nodemanager import NodeManagerService

import theseus.node

from theseus.test import test_node


class SingleNodeRoutingTableTests(unittest.TestCase):
    def setUp(self):
        test_node.NodeTests.setUp(self)  # apply NodeService testing harness

        theseus.node.NodeService.updateID = lambda _: None
        theseus.node.NodeService._listen = lambda _, __: None

        self.node_manager = NodeManagerService(
                node_ids=[NodeID(b'\xAA'*20, verify=False)]
                )
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
        self.assertTrue(self.table.insert(  # redundant insert
                IPv4Address("TCP", "127.0.0.1", 2050),
                NodeID(b'\x02' * 20, verify=False)
                ))

        self.assertIn(IPv4Address("TCP", "127.0.0.1", 2048), self.table)
        self.assertIn(IPv4Address("TCP", "127.0.0.1", 2049), self.table)
        self.assertIn(IPv4Address("TCP", "127.0.0.1", 2050), self.table)

    def test_routing_query(self):
        self.test_insert()
        self.assertEqual(
                self.table.query(b'\x00'*20),
                [
                    IPv4Address("TCP", "127.0.0.1", 2048),
                    IPv4Address("TCP", "127.0.0.1", 2049),
                    IPv4Address("TCP", "127.0.0.1", 2050),
                ])

    def test_remove(self):
        self.test_insert()

        self.assertTrue(self.table.remove(IPv4Address("TCP", "127.0.0.1", 2049)))
        self.assertFalse(self.table.remove(IPv4Address("TCP", "127.0.0.1", 2051)))  # not in table

        self.assertIn(IPv4Address("TCP", "127.0.0.1", 2048), self.table)
        self.assertNotIn(IPv4Address("TCP", "127.0.0.1", 2049), self.table)
        self.assertIn(IPv4Address("TCP", "127.0.0.1", 2050), self.table)

    def test_duplicate_id_insert(self):
        self.assertTrue(self.table.insert(
                IPv4Address("TCP", "127.0.0.1", 2048),
                NodeID(b'\x00' * 20, verify=False)
                ))
        self.assertFalse(self.table.insert(
                IPv4Address("TCP", "127.0.0.1", 4096),
                NodeID(b'\x00' * 20, verify=False)
                ))

    def test_split(self):
        for i in range(self.table.k):
            self.assertTrue(self.table.insert(
                IPv4Address("TCP", "127.0.0.1", 2048+i),
                NodeID(b'\x00'*19 + bytes([i]), verify=False)
                ))

        i += 1
        self.assertFalse(self.table.insert(
            IPv4Address("TCP", "127.0.0.1", 2048+i),
            NodeID(b'\x00'*19 + bytes([i]), verify=False)
            ))

        self.assertTrue(self.table.insert(
            IPv4Address("TCP", "127.0.0.1", 4096),
            NodeID(b'\xAA'*19+b'\x00', verify=False)
            ))

class MultiNodeRoutingTableTests(unittest.TestCase):
    def setUp(self):
        test_node.NodeTests.setUp(self)  # apply NodeService testing harness

        theseus.node.NodeService.updateID = lambda _: None
        theseus.node.NodeService._listen = lambda _, __: None

        self.node_manager = NodeManagerService(
            node_ids=[
                NodeID(b'\x17'*20, None, verify=False),
                NodeID(b'\x34'*20, None, verify=False),
                NodeID(b'\x69'*20, None, verify=False),
                NodeID(b'\xAA'*20, None, verify=False),
                NodeID(b'\xCC'*20, None, verify=False),
            ])
        self.node_manager.startService()

        self.table = RoutingTable(self.node_manager)

    def tearDown(self):
        test_node.NodeTests.tearDown(self)  # remove NodeService harness

    test_insert = SingleNodeRoutingTableTests.test_insert
    test_remove = SingleNodeRoutingTableTests.test_remove

    def test_splits(self):
        # 0x0000... IDs
        for i in range(self.table.k):
            self.assertTrue(self.table.insert(
                IPv4Address("TCP", "127.0.0.1", 2000+i),
                NodeID(b'\x00'*19 + bytes([i]), verify=False)
                ))
        i += 1
        self.assertFalse(self.table.insert(
            IPv4Address("TCP", "127.0.0.1", 2000+i),
            NodeID(b'\x00'*19 + bytes([i]), verify=False)
            ))

        # 0x1000... IDs
        for i in range(self.table.k):
            self.assertTrue(self.table.insert(
                IPv4Address("TCP", "127.0.0.1", 3000+i),
                NodeID(b'\x10' + b'\x00'*18 + bytes([i]), verify=False)
                ))
        i += 1
        self.assertFalse(self.table.insert(
            IPv4Address("TCP", "127.0.0.1", 3000+i),
            NodeID(b'\x10' + b'\x00'*18 + bytes([i]), verify=False)
            ))

        # 0x1700... IDs
        for i in range(self.table.k):
            self.assertTrue(self.table.insert(
                IPv4Address("TCP", "127.0.0.1", 4000+i),
                NodeID(b'\x17' + b'\x00'*18 + bytes([i]), verify=False)
                ))
        i += 1
        self.assertFalse(self.table.insert(
            IPv4Address("TCP", "127.0.0.1", 4000+i),
            NodeID(b'\x17' + b'\x00'*18 + bytes([i]), verify=False)
            ))

        # 0x171700... IDs
        for i in range(self.table.k):
            self.assertTrue(self.table.insert(
                IPv4Address("TCP", "127.0.0.1", 5000+i),
                NodeID(b'\x17\x17' + b'\x00'*17 + bytes([i]), verify=False)
                ))
        i += 1
        self.assertFalse(self.table.insert(
            IPv4Address("TCP", "127.0.0.1", 5000+i),
            NodeID(b'\x17' + b'\x00'*18 + bytes([i]), verify=False)
            ))

        # 0xCCFF... IDs
        for i in range(self.table.k):
            self.assertTrue(self.table.insert(
                IPv4Address("TCP", "127.0.0.1", 6000+i),
                NodeID(b'\xCC' + b'\xFF'*18 + bytes([i]), verify=False)
                ))
        i += 1
        self.assertFalse(self.table.insert(
            IPv4Address("TCP", "127.0.0.1", 6000+i),
            NodeID(b'\xCC' + b'\xFF'*18 + bytes([i]), verify=False)
            ))

        # 0xCC00... IDs  (only k/2 of them tho)
        for i in range(self.table.k//2):
            self.assertTrue(self.table.insert(
                IPv4Address("TCP", "127.0.0.1", 7000+i),
                NodeID(b'\xCC' + b'\x00'*18 + bytes([i]), verify=False)
                ))

    def test_hard_routing_queries(self):
        self.test_splits()

        self.assertEqual(
                self.table.query(b'\x00'*20),
                [
                    IPv4Address("TCP", "127.0.0.1", 2000+i)
                    for i in range(self.table.k)
                ])

        self.assertEqual(
                self.table.query(b'\x17' + b'\x00'*19),
                [
                    IPv4Address("TCP", "127.0.0.1", 4000+i)
                    for i in range(self.table.k)
                ])

        self.assertEqual(
                self.table.query(b'\xCC' + b'\x00'*19),
                [
                    IPv4Address("TCP", "127.0.0.1", 7000+i)
                    for i in range(self.table.k//2)
                ] + [
                    IPv4Address("TCP", "127.0.0.1", 6000+i)
                    for i in range(self.table.k//2)
                ])

        self.assertEqual(
                self.table.query(b'\xCC' + b'\xFF'*19),
                [
                    IPv4Address("TCP", "127.0.0.1", 6000+i)
                    for i in range(self.table.k)
                ][::-1]
                )
