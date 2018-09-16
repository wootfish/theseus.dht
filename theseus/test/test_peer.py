from twisted.trial import unittest
from twisted.test.proto_helpers import _FakePort
from twisted.internet.defer import DeferredList

from theseus.peer import PeerService


class PeerTests(unittest.TestCase):
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
        self.assertEqual(len(peer.node_addrs), 0)

        def cb(results):
            self.assertEqual(len(results), peer.num_nodes)
            self.assertTrue(all(status for status, result in results))

        dl = DeferredList(peer._local_node_addr_workers)
        dl.addCallback(cb)

        return dl
