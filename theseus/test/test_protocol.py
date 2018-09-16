from twisted.trial import unittest
from twisted.test import proto_helpers

from theseus.protocol import DHTProtocol


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.proto = DHTProtocol()
        self.transport = proto_helpers.StringTransportWithDisconnection()
        self.transport.protocol = self.proto
        self.proto.makeConnection(self.transport)

    def test_rejecting_garbage(self):
        self.proto.stringReceived(b'holy smokes')
        self.assertFalse(self.transport.connected)
