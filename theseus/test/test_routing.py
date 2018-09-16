from twisted.trial import unittest

from theseus.routing import RoutingTable

from theseus.nodeaddr import NodeAddress


class RoutingTests(unittest.TestCase):
    def test_basic_inserts(self):
        k = 8
        table = RoutingTable()
        table.k = k
        good_addrs = [bytes([i])*20 for i in range(k)]
        for addr in good_addrs:
            self.assertTrue(table.insert(None, NodeAddress(addr, None)))
        self.assertFalse(table.insert(None, NodeAddress(b'\xFF'*20, None)))
        self.assertEqual(good_addrs, [entry.node_addr.addr for entry in table.root.get_contents()])

    def test_basic_splits(self):
        class DummyPeer:
            node_addrs = [NodeAddress(b'\x00'*20, None), NodeAddress(b'\xFF' + b'\x00'*19, None)]

        k = 8
        table = RoutingTable(DummyPeer())
        table.k = k

        low_addrs = [bytes([i])*20 for i in range(k)]
        med_addrs = [b'\xA0\x00' + bytes([i])*18 for i in range(k)]
        high_addrs = [b'\xFF' + bytes([i])*19 for i in range(k)]

        for addr in low_addrs:
            self.assertTrue(table.insert(None, NodeAddress(addr, None)))
        for addr in med_addrs:
            self.assertTrue(table.insert(None, NodeAddress(addr, None)))
        for addr in high_addrs:
            self.assertTrue(table.insert(None, NodeAddress(addr, None)))

        self.assertFalse(table.insert(None, NodeAddress(b'\x81'+bytes(19), None)))
        self.assertFalse(table.insert(None, NodeAddress(b'\x82'+bytes(19), None)))
        self.assertEqual(
                low_addrs + med_addrs + high_addrs,
                [entry.node_addr.addr for entry in table.root.get_contents()]
                )

    def test_basic_queries(self):
        class DummyPeer:
            node_addrs = [NodeAddress(b'\x00'*20, None), NodeAddress(b'\xFF' + b'\x00'*19, None)]

        k = 8
        table = RoutingTable(DummyPeer())
        table.k = k

        low_addrs = [bytes([i])*20 for i in range(k)]
        med_addrs = [b'\xA0\x00' + bytes([i])*18 for i in range(k)]
        high_addrs = [b'\xFF' + bytes([i])*19 for i in range(k)]

        for addr in low_addrs:
            self.assertTrue(table.insert(None, NodeAddress(addr, None)))
        for addr in med_addrs:
            self.assertTrue(table.insert(None, NodeAddress(addr, None)))
        for addr in high_addrs:
            self.assertTrue(table.insert(None, NodeAddress(addr, None)))

        self.assertEqual(
                low_addrs,
                [entry.node_addr.addr for entry in table.query(b'\x00'*20, lookup_size=k)]
                )
        self.assertEqual(
                low_addrs + med_addrs[:4],
                [entry.node_addr.addr for entry in table.query(b'\x00'*20, lookup_size=k+4)]
                )
        self.assertEqual(
                high_addrs + [med_addrs[-1]],
                [entry.node_addr.addr for entry in table.query(b'\xF0\x00\x07' + bytes(17), lookup_size=k+1)]
                )
