from twisted.trial import unittest
from twisted.internet.defer import Deferred

from theseus.statstracker import StatsTracker
from theseus.routing import RoutingEntry
from theseus.nodeaddr import NodeAddress
from theseus.constants import k

from unittest.mock import Mock


class StatsTrackerTests(unittest.TestCase):
    def setUp(self):
        self.mock_peer = Mock()
        self.s = StatsTracker(self.mock_peer)
        self.s.start()

    def tearDown(self):
        self.s.stop()

    def test_size_estimation(self):
        for i in range(self.s.min_sample_size):
            target = bytes([i] + [0]*19)
            addrs = [NodeAddress(bytes([i, j+1] + [0]*18), b'preimage') for j in range(k)]
            entries = [RoutingEntry(contact_info=None, node_addr=addr) for addr in addrs]

            d = Deferred()
            self.s.register_lookup(d, target)
            d.callback(entries)

        estimate = self.s.get_size()
        self.assertEqual(estimate, 65536.0)
