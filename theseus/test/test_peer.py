from twisted.trial import unittest
from twisted.test.proto_helpers import _FakePort
from twisted.internet.defer import DeferredList, succeed, inlineCallbacks
from twisted.internet.task import Clock
from twisted.internet.address import IPv4Address
from twisted.test.proto_helpers import MemoryReactor, RaisingMemoryReactor, StringTransportWithDisconnection
from twisted.plugin import IPlugin
from twisted import plugins

from zope.interface import implementer

from theseus.contactinfo import ContactInfo
from theseus.peer import PeerService
from theseus.peertracker import PeerState
from theseus.nodemanager import NodeManager
from theseus.enums import MAX_VERSION, LISTEN_PORT, PEER_KEY, ADDRS, CONNECTING, INITIATOR
from theseus.plugins import IPeerSource
from theseus.nodeaddr import NodeAddress, Preimage
from theseus.lookup import AddrLookup


class PeerTests(unittest.TestCase):
    def setUp(self):
        class Fake_RNG:
            def randrange(self, lower, upper):
                return 1337

        def fake_listen(_, port):
            self.assertEqual(port, 1337)
            return _FakePort(IPv4Address("TCP", "127.0.0.1", 1337))

        self._callLater = NodeManager.callLater
        self._rng = PeerService._rng
        self._listen = PeerService._listen
        self._reactor = PeerState._reactor
        self._lookup_clock = AddrLookup.clock

        self.clock = Clock()
        self.memory_reactor = MemoryReactor()
        NodeManager.callLater = self.clock.callLater
        PeerService._rng = Fake_RNG()
        PeerService._listen = fake_listen
        PeerState._reactor = self.memory_reactor
        AddrLookup.clock = self.clock

        self.peer = PeerService()

    def tearDown(self):
        NodeManager.callLater = self._callLater
        PeerService._rng = self._rng
        PeerService._listen = self._listen
        PeerState._reactor = self._reactor
        self.peer.stopService()
        AddrLookup.clock = self._lookup_clock
        return self.peer.node_manager.get_addrs()

    def test_startup(self):
        self.peer.startService()
        self.assertEqual(self.peer.listen_port, 1337)
        self.assertEqual(len(self.clock.getDelayedCalls()), 0)

        d = self.peer.node_manager.get_addrs()
        def cb(results):
            self.assertEqual(len(results), self.peer.node_manager.num_nodes)
            self.assertEqual(len(self.clock.getDelayedCalls()), 5+5)  # 5 for expiring the nodes, 5 for looking them up
        d.addCallback(cb)

        return d

    def test_get_info(self):
        self.assertEqual(
                self.successResultOf(self.peer.get_info(MAX_VERSION)),
                "n/a")
        self.assertEqual(
                self.successResultOf(self.peer.get_info(LISTEN_PORT)),
                None)
        self.assertEqual(
                self.successResultOf(self.peer.get_info(PEER_KEY)),
                self.peer.peer_key.public_bytes)

        d = self.peer.get_info(ADDRS)
        self.assertFalse(d.called)
        d.addCallback(lambda addrs: self.assertTrue(all((
            addrs == [addr.as_bytes() for addr in self.peer.node_manager.node_addrs],
            len(addrs) == 5))))
        self.peer.node_manager.start()
        return d

    def test_cnxn_attempt(self):
        self.peer.startService()
        self.addCleanup(self.peer.node_manager.get_addrs)
        target = ContactInfo('127.0.0.1', 12345, self.peer.peer_key) # this is lazy & recycles the peer's key as the remote key, but... hey
        d = self.peer.get_peer(target).connect()
        d2 = self.peer.get_peer(target).connect()
        self.assertEqual(d, d2)
        self.assertEqual(len(self.memory_reactor.tcpClients), 1)

    def test_doomed_cnxn_attempt(self):
        PeerState._reactor = RaisingMemoryReactor()
        self.peer.startService()
        self.addCleanup(self.peer.node_manager.get_addrs)
        target = ContactInfo('127.0.0.1', 12345, self.peer.peer_key)
        d = self.peer.get_peer(target).connect()
        self.failureResultOf(d)

    def test_cnxn_success(self):
        self.test_cnxn_attempt()
        target = ContactInfo('127.0.0.1', 12345, self.peer.peer_key) # this is lazy & recycles the peer's key as the remote key, but... hey
        d = self.peer.get_peer(target).connect()
        self.assertEqual(len(self.memory_reactor.tcpClients), 1)

        factory = self.memory_reactor.tcpClients[0][2]
        transport = StringTransportWithDisconnection()
        factory.buildProtocol(IPv4Address("TCP", target.host, target.port)).makeConnection(transport)
        self.p = self.successResultOf(d)
        self.assertEqual(self.p.connected, 0)  # this won't connect until after noise handshake completion
        self.assertEqual(self.p.transport, None)
        self.assertEqual(self.p.peer_state.state, CONNECTING)
        self.assertEqual(self.p.peer_state.role, INITIATOR)

    @inlineCallbacks
    def test_info_updates_1(self):
        self.test_cnxn_success()
        self.assertTrue(self.peer.maybe_update_info(self.p, ADDRS.value, []))
        _ = yield self.peer.node_manager.get_addrs()

        # get some fresh node addresses
        node_manager = NodeManager(3)
        node_manager.start()
        addrs = yield node_manager.get_addrs()

        # install a dummy transport (good god this code is ugly)
        self.p.transport = type("DummyTransport", (object,), {
            "getPeer": (lambda: type("DummyPeer", (object,), {"host": "127.0.0.1"}))
            })
        self.assertTrue(self.peer.maybe_update_info(self.p, ADDRS.value,
            [addr.as_bytes() for addr in addrs]
            ))

    @inlineCallbacks
    def test_info_updates_2(self):
        # get some fresh node addresses, this time _before_ generating the local peer's addrs
        node_manager = NodeManager(3)
        node_manager.start()
        addrs = yield node_manager.get_addrs()

        self.test_cnxn_success()
        self.assertTrue(self.peer.maybe_update_info(self.p, ADDRS.value, []))

        # install a dummy transport (good god this code is ugly)
        self.p.transport = type("DummyTransport", (object,), {
            "getPeer": (lambda: type("DummyPeer", (object,), {"host": "127.0.0.1"}))
            })
        self.assertTrue(self.peer.maybe_update_info(self.p, ADDRS.value,
            [addr.as_bytes() for addr in addrs]
            ))
