import twisted.internet.base

from twisted.logger import Logger
from twisted.trial import unittest
from twisted.test.proto_helpers import _FakePort
from twisted.internet.defer import DeferredList, succeed, inlineCallbacks
from twisted.internet.task import Clock, deferLater
from twisted.internet.address import IPv4Address
from twisted.internet import reactor
from twisted.test.proto_helpers import MemoryReactor, RaisingMemoryReactor, StringTransport
from twisted.plugin import IPlugin
from twisted import plugins
from twisted.protocols.policies import WrappingFactory
from twisted.internet.protocol import Factory

from zope.interface import implementer

from theseus.contactinfo import ContactInfo
from theseus.peer import PeerService
from theseus.peertracker import PeerState
from theseus.nodemanager import NodeManager
from theseus.enums import MAX_VERSION, LISTEN_PORT, PEER_KEY, ADDRS, CONNECTING, INITIATOR, RESPONDER
from theseus.plugins import IPeerSource
from theseus.nodeaddr import NodeAddress, Preimage
from theseus.lookup import AddrLookup
from theseus.protocol import DHTProtocol
from theseus.noisewrapper import NoiseWrapper, NoiseSettings
from theseus.constants import timeout_window
from theseus.hasher import hasher


class PeerTests(unittest.TestCase):
    log = Logger()

    def setUp(self):
        #twisted.internet.base.DelayedCall.debug = True
        class Fake_RNG:
            def randrange(self, lower, upper):
                return 1337

        def fake_listen(_, port):
            self.assertEqual(port, 1337)
            return _FakePort(IPv4Address("TCP", "127.0.0.1", 1337))

        self._rng = PeerService._rng
        self._listen = PeerService._listen
        self._reactor = PeerState._reactor

        self.clock = Clock()
        PeerState._clock = self.clock
        NodeManager._clock = self.clock
        AddrLookup._clock = self.clock

        self.memory_reactor = MemoryReactor()
        PeerState._reactor = self.memory_reactor
        PeerService._rng = Fake_RNG()
        PeerService._listen = fake_listen

        self.num_nodes = 1

        self.peer = PeerService(self.num_nodes)

    @inlineCallbacks
    def tearDown(self):
        self.log.info("==== PeerTests: running tearDown")

        _ = yield hasher.exhaust()

        self.clock.pump([60*10]*120)
        self.peer.stopService()
        self.clock.pump([60*10]*120)

        self.log.info("==== PeerTests: done pumping clock")

        PeerService._rng = self._rng
        PeerService._listen = self._listen
        PeerState._reactor = self._reactor
        PeerState._clock = self._reactor
        NodeManager._clock = self._reactor
        AddrLookup._clock = self._reactor

    def _start_service(self):
        self.peer.startService()
        self.addCleanup(self.clock.advance, timeout_window)

    @inlineCallbacks
    def test_startup(self):
        self._start_service()
        self.assertEqual(self.peer.listen_port, 1337)
        self.assertEqual(len(self.clock.getDelayedCalls()), 0)

        results = yield self.peer.node_manager.get_addrs()
        self.assertEqual(len(results), self.num_nodes)
        self.assertEqual(len(self.peer._addr_lookups), self.num_nodes)
        self.assertEqual(len(self.peer.node_manager.looping_calls), self.num_nodes)

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
            len(addrs) == self.num_nodes))))
        self.peer.node_manager.start()
        return d

    def test_cnxn_attempt(self):
        self._start_service()
        self.addCleanup(self.peer.node_manager.get_addrs)
        target = ContactInfo('127.0.0.1', 12345, self.peer.peer_key) # this is lazy & recycles the peer's key as the remote key, but... hey
        d = self.peer.get_peer(target).connect()
        d2 = self.peer.get_peer(target).connect()
        self.assertEqual(d, d2)
        self.assertEqual(len(self.memory_reactor.tcpClients), 1)

    def test_doomed_cnxn_attempt(self):
        PeerState._reactor = RaisingMemoryReactor()
        self._start_service()
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
        self.t = StringTransport(IPv4Address('TCP', '127.0.0.1', 1337), IPv4Address('TCP', '127.0.0.1', 12345))
        self.wrapper = factory.buildProtocol(IPv4Address("TCP", target.host, target.port))
        self.wrapper.makeConnection(self.t)
        self.p = self.successResultOf(d)
        self.assertEqual(self.p.connected, 0)  # this won't connect until after noise handshake completion
        self.assertEqual(self.p.transport, None)
        self.assertEqual(self.p.peer_state.state, CONNECTING)
        self.assertEqual(self.p.peer_state.role, INITIATOR)
        self.assertFalse(self.t.disconnecting)

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

        node_manager.stop()

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

        node_manager.stop()

    def _do_handshake(self):
        self.test_cnxn_success()

        # make a second protocol for the first one to talk to
        # (so we don't have to handle Noise msgs manually)
        host = IPv4Address("TCP", "127.0.0.1", 1337)
        factory = WrappingFactory.forProtocol(NoiseWrapper, Factory.forProtocol(DHTProtocol))
        self.wrapper2 = factory.buildProtocol(host)
        self.wrapper2.settings = NoiseSettings(RESPONDER, local_static=self.peer.peer_key)
        self.t2 = StringTransport(IPv4Address("TCP", "127.0.0.1", 12345), IPv4Address("TCP", "127.0.0.1", 1337))
        self.wrapper2.makeConnection(self.t2)
        self.p2 = self.wrapper2.wrappedProtocol

        self.wrapper2.dataReceived(self.t.value())
        self.t.clear()

        self.wrapper.dataReceived(self.t2.value())
        self.t2.clear()

        self.assertFalse(self.wrapper.transport.disconnecting)
        self.assertFalse(self.wrapper2.transport.disconnecting)

        self.assertTrue(self.p.connected)
        self.assertTrue(self.p2.connected)

        self.addCleanup(self.p.setTimeout, None)
        self.addCleanup(self.p2.setTimeout, None)

    @inlineCallbacks
    def test_handshake_and_introduction(self):
        self._do_handshake()

        addrs = yield self.peer.node_manager.get_addrs()
        _ = yield deferLater(reactor, 0, lambda: None)  # wait for everything else that hooked get_addrs to run

        self.p2.query_handlers[b'info'] = lambda d: self.assertTrue(
                sorted(d.keys()) == [b'info', b'keys']
                and sorted(d[b'keys']) == [b'addrs', b'listen_port', b'max_version', b'peer_key']
                and sorted(d[b'info'].keys()) == [b'addrs', b'listen_port', b'max_version', b'peer_key']
                and sorted(d[b'info'][b'addrs']) == sorted(addr.as_bytes() for addr in addrs)
                and d[b'info'][b'listen_port'] == 1337
                and d[b'info'][b'max_version'] == b'n/a'  # lol
                and d[b'info'][b'peer_key'] == self.peer.peer_key.public_bytes
                ) and {'info': {'addrs': [], 'listen_port': 12345, 'max_version': 'n/a', 'peer_key': self.peer.peer_key.public_bytes}}

        self.wrapper2.dataReceived(self.t.value())
        self.t.clear()
        self.wrapper.dataReceived(self.t2.value())
        self.t2.clear()

        self.assertEqual(self.p.peer_state.info.get(PEER_KEY).public_bytes, self.peer.peer_key.public_bytes)
        self.assertEqual(self.p.peer_state.info.get(LISTEN_PORT), 12345)
        self.assertEqual(self.p.peer_state.info.get(ADDRS), [])

        self.assertEqual(len(self.p.open_queries), 0)
        self.assertEqual(len(self.p2.open_queries), 0)

    @inlineCallbacks
    def test_put_and_get(self):
        self._do_handshake()

        self.log.info("==== handshake done")

        _ = yield self.peer.node_manager.get_addrs()  # we won't have data stores til we have addrs :)

        self.t.clear()
        self.t2.clear()

        self.p2.response_handlers[b'put'] = lambda d: self.assertTrue(len(d) == 1 and type(d[b'd']) is int and d[b'd'] > 0)
        self.p2.response_handlers[b'get'] = lambda d: self.assertTrue(len(d) == 1 and d[b'data'] == [b'bearseatgoatsandgoatseatoats'])

        self.p2.send_query(b'put', {b'addr': bytes(20), b'data': b'bearseatgoatsandgoatseatoats'})
        self.wrapper.dataReceived(self.t2.value())
        self.t2.clear()
        self.wrapper2.dataReceived(self.t.value())
        self.t.clear()

        self.p2.send_query(b'get', {b'addr': bytes(20)})
        self.wrapper.dataReceived(self.t2.value())
        self.t2.clear()
        self.wrapper2.dataReceived(self.t.value())
        self.t.clear()

        self.assertFalse(self.wrapper.transport.disconnecting)
        self.assertFalse(self.wrapper2.transport.disconnecting)

        self.assertTrue(self.p.connected)
        self.assertTrue(self.p2.connected)
