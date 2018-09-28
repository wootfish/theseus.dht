from twisted.trial import unittest

from theseus.routing import RoutingTable

from theseus.nodeaddr import NodeAddress

from pprint import pprint


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.table = RoutingTable()

    def test_basic_inserts(self):
        k = 8
        self.table.k = k
        good_addrs = [bytes([i])*20 for i in range(k)]
        for addr in good_addrs:
            self.assertTrue(self.table.insert(None, NodeAddress(addr, None)))
        self.assertFalse(self.table.insert(None, NodeAddress(b'\xFF'*20, None)))
        self.assertEqual(good_addrs, [entry.node_addr.addr for entry in self.table.root.get_contents()])

    def test_basic_splits(self):
        k = 8
        self.table = RoutingTable([NodeAddress(b'\x00'*20, None), NodeAddress(b'\xFF' + b'\x00'*19, None)])
        self.table.k = k

        low_addrs = [bytes([i])*20 for i in range(k)]
        med_addrs = [b'\xA0\x00' + bytes([i])*18 for i in range(k)]
        high_addrs = [b'\xFF' + bytes([i])*19 for i in range(k)]

        for addr in low_addrs:
            self.assertTrue(self.table.insert(None, NodeAddress(addr, None)))
        for addr in med_addrs:
            self.assertTrue(self.table.insert(None, NodeAddress(addr, None)))
        for addr in high_addrs:
            self.assertTrue(self.table.insert(None, NodeAddress(addr, None)))

        self.assertFalse(self.table.insert(None, NodeAddress(b'\x81'+bytes(19), None)))
        self.assertFalse(self.table.insert(None, NodeAddress(b'\x82'+bytes(19), None)))
        self.assertEqual(
                low_addrs + med_addrs + high_addrs,
                [entry.node_addr.addr for entry in self.table.root.get_contents()]
                )

    def test_basic_queries(self):
        k = 8
        self.table = RoutingTable([NodeAddress(b'\x00'*20, None), NodeAddress(b'\xFF' + b'\x00'*19, None)])
        self.table.k = k

        low_addrs = [bytes([i])*20 for i in range(k)]
        med_addrs = [b'\xA0\x00' + bytes([i])*18 for i in range(k)]
        high_addrs = [b'\xFF' + bytes([i])*19 for i in range(k)]

        for addr in low_addrs:
            self.assertTrue(self.table.insert(None, NodeAddress(addr, None)))
        for addr in med_addrs:
            self.assertTrue(self.table.insert(None, NodeAddress(addr, None)))
        for addr in high_addrs:
            self.assertTrue(self.table.insert(None, NodeAddress(addr, None)))

        self.assertEqual(
                low_addrs,
                [entry.node_addr.addr for entry in self.table.query(b'\x00'*20, lookup_size=k)]
                )
        self.assertEqual(
                low_addrs + med_addrs[:4],
                [entry.node_addr.addr for entry in self.table.query(b'\x00'*20, lookup_size=k+4)]
                )
        self.assertEqual(
                high_addrs + [med_addrs[-1]],
                [entry.node_addr.addr for entry in self.table.query(b'\xF0\x00\x07' + bytes(17), lookup_size=k+1)]
                )

    def test_basic_reloads(self):
        k = 8
        self.table.reload()
        self.assertTrue(self.table.insert(None, NodeAddress(bytes(20), None)))
        self.table.reload()
        self.table.reload()
        self.table.reload()

    def test_complex_reloads(self):
        self.test_basic_queries()
        contents = self.table.root.get_contents()

        self.table.reload(self.table.local_addrs)
        self.assertEqual(contents, self.table.root.get_contents())

        self.table.reload(self.table.local_addrs + [NodeAddress(b'\x420'*10, None)])
        self.assertEqual(contents, self.table.root.get_contents())

        self.table.reload([self.table.local_addrs[0]])
        # we don't actually know exactly which nodes will be in here: some get
        # dropped because we're down to one node ID. which ones depends on the
        # ordering after they're shuffled with an algorithm backed by a CSPRNG.
        self.assertEqual(len(self.table.root.get_contents()), 16)
