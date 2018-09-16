from twisted.trial import unittest

from theseus.routing import RoutingTable


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.table = RoutingTable()
