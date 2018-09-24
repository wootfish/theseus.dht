from twisted.trial import unittest
from twisted.test.proto_helpers import _FakePort
from twisted.internet.defer import DeferredList
from twisted.internet.task import Clock

from theseus.peer import PeerService
from theseus.nodemanager import NodeManager


class PeerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self._callLater = NodeManager.callLater
        NodeManager.callLater = self.clock.callLater

        self._randrange = PeerService._randrange
        self._listen = PeerService._listen

    def tearDown(self):
        NodeManager.callLater = self._callLater
        PeerService._randrange = self._randrange
        PeerService._listen = self._listen

    def test_startup(self):
        def fake_randrange(_, lower, upper):
            return 1337

        def fake_listen(_, port):
            self.assertEqual(port, 1337)
            return _FakePort('127.0.0.1')

        PeerService._randrange = fake_randrange
        PeerService._listen = fake_listen

        peer = PeerService()
        peer.startService()
        self.assertEqual(peer.listen_port, 1337)
        self.assertEqual(len(self.clock.getDelayedCalls()), 0)

        d = peer.node_manager.get_addrs()
        def cb(results):
            self.assertEqual(len(results), peer.node_manager.num_nodes)
            self.assertEqual(len(self.clock.getDelayedCalls()), 5)
        d.addCallback(cb)

        return d
