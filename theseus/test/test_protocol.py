from twisted.trial import unittest
from twisted.test import proto_helpers
from twisted.internet.defer import succeed

from theseus.protocol import DHTProtocol
from theseus.errors import Error201, Error202
from theseus.enums import DHTInfoKeys
from theseus.bencode import bencode, bdecode
from theseus.test.util import netstringify
from theseus.routing import RoutingEntry
from theseus.contactinfo import ContactInfo
from theseus.nodeaddr import NodeAddress, Preimage

from noise.functions import KeyPair25519


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.proto = DHTProtocol()
        self.transport = proto_helpers.StringTransportWithDisconnection()
        self.transport.protocol = self.proto
        self.proto.makeConnection(self.transport)
        self.proto.setTimeout(None)  # we're testing DHTProtocol here, not TimeoutMixin

    def test_rejecting_garbage(self):
        self.proto.stringReceived(b'holy smokes')
        self.assertFalse(self.transport.connected)

    def test_get_keys_without_peer(self):
        d = self.proto.get_local_keys()
        self.assertFailure(d, Error202)
        return d

    def test_get_no_local_keys(self):
        self.assertEqual(
                self.successResultOf(self.proto.get_local_keys([])),
                {})

    def test_get_info_keys_with_dummy_peer(self):
        class DummyPeer:
            def get_info(self, key):
                # MAX_VERSION and ADDRS return values, LISTEN_PORT and PEER_KEY return Deferreds
                if key[0] % 2 == 0:
                    return succeed(key[0])
                return key[0]

        self.proto.local_peer = DummyPeer()
        d = self.proto.get_local_keys()
        def cb(keys):
            self.assertEqual(len(keys), len(DHTInfoKeys))
            for key in DHTInfoKeys:
                self.assertIn(key.value, keys)
                self.assertEqual(key.value[0], keys[key.value])
        d.addCallback(cb)
        return d

    def test_simple_info_query(self):
        self.assertEqual(
                self.successResultOf(self.proto.info({})),
                {'info': {}})

    def test_bad_remote_info(self):
        with self.assertRaises(Error201):
            self.proto.info({b'info': b'schminfo'})

    def test_bad_local_keys(self):
        with self.assertRaises(Error201):
            self.proto.info({b'keys': b'schmees'})

    def test_timeout(self):
        self.proto.timeoutConnection()
        self.assertFalse(self.transport.connected)

    def test_find_query_simple_1(self):
        with self.assertRaises(Error201):
            self.proto.find({})

    def test_find_query_simple_2(self):
        self.assertEqual(self.proto.find({b'addr': bytes(20)}), {"nodes": []})

    def test_find_query_simple_3(self):
        ip = '127.127.127.127'
        port = 2018
        key = KeyPair25519.from_public_bytes(b'z'*32)
        addr = bytes(20)
        ts = bytes(4)
        entropy = bytes(6)

        class DummyRoutingTable:
            def query(self, addr):
                contact = ContactInfo(ip, port, key)
                preimage = Preimage(ts, ip, entropy)
                address = NodeAddress(addr, preimage)
                entry = RoutingEntry(contact, address)
                return [entry]

        class DummyPeer:
            routing_table = DummyRoutingTable()

        contact = ContactInfo(ip, port, key)
        preimage = Preimage(ts, ip, entropy)
        address = NodeAddress(addr, preimage)
        entry = RoutingEntry(contact, address)

        self.proto.local_peer = DummyPeer()
        self.assertEqual(self.proto.find({b'addr': bytes(20)}), {"nodes": [entry.as_bytes()]})
