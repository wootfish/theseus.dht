from twisted.trial import unittest

from theseus.routing import RoutingTable

from theseus.nodeaddr import NodeAddress
from theseus.constants import k


class RoutingTests(unittest.TestCase):
    def test_basic_inserts(self):
        table = RoutingTable()
        good_addrs = [bytes([i])*20 for i in range(k)]
        for addr in good_addrs:
            self.assertTrue(table.insert(None, NodeAddress(addr, None)))
        self.assertFalse(table.insert(None, NodeAddress(b'\xFF'*20, None)))
        self.assertEqual(good_addrs, [entry.node_addr.addr for entry in table.root.get_contents()])

    def test_basic_splits(self):
        class DummyPeer:
            node_addrs = [NodeAddress(b'\x00'*20, None), NodeAddress(b'\xFF' + b'\x00'*19, None)]

        table = RoutingTable(DummyPeer())
        low_addrs = [bytes([i])*20 for i in range(k)]
        for addr in low_addrs:
            self.assertTrue(table.insert(None, NodeAddress(addr, None)))

        high_addrs = [b'\xFF' + bytes([i])*19 for i in range(k)]
        for addr in high_addrs:
            self.assertTrue(table.insert(None, NodeAddress(addr, None)))

        med_addrs = [b'\xA0\x00' + bytes([i])*18 for i in range(k)]
        #med_addrs += [b'\x80\x00' + bytes([i])*18 for i in range(k)]

        for addr in med_addrs:
            self.assertTrue(table.insert(None, NodeAddress(addr, None)))

        self.assertFalse(table.insert(None, NodeAddress(b'\x81'+bytes(19), None)))
        self.assertFalse(table.insert(None, NodeAddress(b'\x82'+bytes(19), None)))
        self.assertEqual(
                low_addrs + med_addrs + high_addrs,
                [entry.node_addr.addr for entry in table.root.get_contents()]
                )
