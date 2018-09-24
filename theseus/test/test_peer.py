from twisted.trial import unittest
from twisted.test.proto_helpers import _FakePort
from twisted.internet.defer import DeferredList
from twisted.internet.task import Clock
from twisted.internet.address import IPv4Address
from twisted.test.proto_helpers import MemoryReactor, RaisingMemoryReactor

from theseus.contactinfo import ContactInfo
from theseus.peer import PeerService
from theseus.peertracker import PeerState
from theseus.nodemanager import NodeManager
from theseus.enums import MAX_VERSION, LISTEN_PORT, PEER_KEY, ADDRS


class PeerTests(unittest.TestCase):
    def setUp(self):
        def fake_randrange(_, lower, upper):
            return 1337

        def fake_listen(_, port):
            self.assertEqual(port, 1337)
            return _FakePort(IPv4Address("TCP", "127.0.0.1", 1337))

        self._callLater = NodeManager.callLater
        self._randrange = PeerService._randrange
        self._listen = PeerService._listen
        self._reactor = PeerState._reactor

        self.clock = Clock()
        self.memory_reactor = MemoryReactor()
        NodeManager.callLater = self.clock.callLater
        PeerService._randrange = fake_randrange
        PeerService._listen = fake_listen
        PeerState._reactor = self.memory_reactor

        self.peer = PeerService()

    def tearDown(self):
        NodeManager.callLater = self._callLater
        PeerService._randrange = self._randrange
        PeerService._listen = self._listen
        PeerState._reactor = self._reactor

        self.peer.stopService()

    def test_startup(self):
        self.peer.startService()
        self.assertEqual(self.peer.listen_port, 1337)
        self.assertEqual(len(self.clock.getDelayedCalls()), 0)

        d = self.peer.node_manager.get_addrs()
        def cb(results):
            self.assertEqual(len(results), self.peer.node_manager.num_nodes)
            self.assertEqual(len(self.clock.getDelayedCalls()), 5)
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
        # this is lazy & recycles the peer's key as the remote key, but... hey
        self.peer.startService()
        target = ContactInfo('127.0.0.1', 12345, self.peer.peer_key)
        d = self.peer.make_cnxn(target)
        d2 = self.peer.make_cnxn(target)
        self.assertEqual(d, d2)
        self.assertEqual(len(self.memory_reactor.tcpClients), 1)
        return self.peer.node_manager.get_addrs()

    def test_cnxn_attempt(self):
        PeerState._reactor = RaisingMemoryReactor()
        # this is lazy & recycles the peer's key as the remote key, but... hey
        self.peer.startService()
        target = ContactInfo('127.0.0.1', 12345, self.peer.peer_key)
        d = self.peer.make_cnxn(target)
        self.failureResultOf(d)

        return self.peer.node_manager.get_addrs()
