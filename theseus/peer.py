from twisted.application.service import Service
from twisted.internet import reactor
from twisted.internet.defer import succeed, fail, maybeDeferred, DeferredList, Deferred
from twisted.internet.error import CannotListenError
from twisted.logger import Logger
from twisted.plugin import getPlugins

from noise.functions import DH, KeyPair25519

from .config import config
from .contactinfo import ContactInfo
from .constants import k
from .enums import DHTInfoKeys, MAX_VERSION, LISTEN_PORT, PEER_KEY, ADDRS, LOW
from .errors import TheseusConnectionError, DuplicateContactError, LookupRetriesExceededError
from .nodeaddr import NodeAddress
from .peertracker import PeerTracker
from .plugins import IPeerSource, IInfoProvider
from .protocol import DHTProtocol
from .routing import RoutingTable
from .nodemanager import NodeManager
from .lookup import AddrLookup
from .statstracker import StatsTracker

from collections import deque
from random import SystemRandom
from socket import inet_aton
from typing import List

import ipaddress


class PeerService(Service):
    """
    Responsible for creating and maintaining all the major components required
    to run a DHT peer. These components are:
    - A routing table
    - A registry and state tracker for remote peers
    - A manager for local node state
    - A peer blacklist
    """

    log = Logger()
    listener = None
    listen_port = None

    blacklist_size = 500

    _rng = SystemRandom()  # broken out for tests

    def __init__(self, num_nodes=5):
        super().__init__()

        self.blacklist = deque(maxlen=self.blacklist_size)
        self.peer_key = self._generate_keypair()

        self.routing_table = RoutingTable()
        self.peer_tracker = PeerTracker(self)
        self.stats_tracker = StatsTracker(self)
        self.node_manager = NodeManager(num_nodes)
        self.node_manager.add_listener(self.on_addr_change)

        self._addr_lookups = []  # type: List[Deferred]

    def startService(self):
        super().startService()
        self.node_manager.start()
        self.listen_port = self._start_listening()

        for peer_source in getPlugins(IPeerSource):
            def cb(peers):
                self.log.info("Peers from {source}: {peers}", source=peer_source, peers=peers)
                for peer in peers:
                    try:
                        self.get_peer(peer).connect()
                    except DuplicateContactError:
                        self.log.warn("Differing contact info records encountered for {host}:{port}", host=peer.host, port=peer.port)

            self.log.info("Loading plugin for peer source {source}", source=peer_source)
            peer_source.get().addCallback(cb)
            peer_source.put(ContactInfo(None, self.listen_port, self.peer_key))

        for info_provider in getPlugins(IInfoProvider):
            DHTProtocol.supported_info_keys.update(info_provider.provided)

        self.stats_tracker.start()

    def stopService(self):
        super().stopService()

        self.log.info("Peer stopping")

        self.node_manager.stop()
        self.stats_tracker.stop()

        for lookup in self._addr_lookups:
            lookup.cancel()

        self.log.info("Peer stopped")

    def on_addr_change(self, new_addrs):
        self.routing_table.reload(new_addrs)  # TODO pass in full list of eligible peers?
        # TODO should we advertise this info change? probably, right?

        # run lookups for all addresses
        for addr in new_addrs:
            # TODO we need a way of allowing infinite retries on fixed
            # intervals, with retries cleanly cancelling on peer.stopService()
            # so we don't have to deal with this retries-exceeded bullshit
            self.do_lookup(addr.addr).addErrback(lambda failure: failure.trap(LookupRetriesExceededError))

    @staticmethod
    def _generate_keypair():
        return DH("ed25519").generate_keypair()

    def _start_listening(self):
        """
        Starts listening on a reasonable port.
        """

        # TODO maybe we should add the option to take a user-specified port (and exit cleanly somehow if it's not available?)

        listen_port_range = config["listen_port_range"]
        ports_to_avoid = config["ports_to_avoid"]

        while True:
            port = self._rng.randrange(*listen_port_range)
            if port in ports_to_avoid:
                continue

            self.log.info("Attempting to listen on port {port}...", port=port)

            try:
                self._listen(port)
            except CannotListenError:
                continue
            else:
                self.log.info("Now listening on port {port} with node key {key}", port=port, key=self.peer_key.public_bytes)
                break

        return port

    def _listen(self, port, reactor=reactor):
        """
        Attempts to start listening for cnxns on the given port.
        Throws a CannotListenError if the port is not available.
        Broken out to simplify tests.
        """
        self.listener = reactor.listenTCP(port, self.peer_tracker)

    def add_to_blacklist(self, host):
        self.log.info("Blacklisting {host}", host=host)
        # TODO add logic to terminate any existing cnxns with blacklisted host
        self.blacklist.append(host)

    def get_peer(self, contact_info):
        if not self.running:
            raise TheseusConnectionError("Service must be running to make connections")

        if contact_info.host in self.blacklist:
            raise TheseusConnectionError("Address blacklisted")

        if ipaddress.IPv4Address(contact_info.host).is_loopback \
                and contact_info.port == self.listen_port:
            raise TheseusConnectionError("Tried to get a remote peer state for ourself")

        peer_state = self.peer_tracker.register_contact(contact_info)
        return peer_state

    def maybe_update_info(self, cnxn, info_key, new_value):
        # returns whether the info update succeeded (true) or failed (false)
        # update attempts on unrecognized keys always fail
        # redundant updates always succeed
        # updates which may succeed or fail in the future return True out of sheer optimism
        self.log.debug("Considering updating {peer} data, {key}: {val}", peer=cnxn._peer, key=info_key, val=new_value)
        peer_state = cnxn.peer_state

        if info_key == ADDRS.value:
            if not InfoPolicy.addrs_valid(new_value, cnxn):
                self.log.debug("Node ID sanity checks failed.")
                return False

            deferreds = [NodeAddress.from_bytes(addr, priority=LOW) for addr in new_value]
            dl = DeferredList(deferreds)
            def cb(l):
                if all(t[0] for t in l):
                    self.log.debug("Updating node IDs for {peer}", peer=cnxn._peer)
                    addrs = [t[1] for t in l]
                    peer_state.info[ADDRS] = addrs
                    self._maybe_do_routing_insert(cnxn)
                else:
                    self.log.debug("Bad node ID(s) from {peer}", peer=cnxn._peer)
                    self.add_to_blacklist(cnxn.transport.getPeer())
            dl.addCallback(cb)
            return True

        elif info_key == LISTEN_PORT.value:
            if not InfoPolicy.port_valid(new_value):
                self.log.debug("Listen port sanity checks failed.")
                return False

            addr = peer_state.host, peer_state.info.get(LISTEN_PORT)
            if (self.peer_tracker.get_from_addr(addr) or peer_state) != peer_state:
                self.log.warn("{peer} - Tried to steal listen addr {addr}!", peer=cnxn._peer, addr=addr)
                cnxn.transport.loseConnection()
                return False
            peer_state.info[LISTEN_PORT] = new_value
            self._maybe_register_contact(cnxn)
            self._maybe_do_routing_insert(cnxn)

        elif info_key == MAX_VERSION.value:
            pass  # we don't need this yet

        elif info_key == PEER_KEY.value:
            if type(new_value) is not bytes or len(new_value) != 32:
                self.log.debug("Peer key sanity checks failed.")
                return False

            try:
                key = KeyPair25519.from_public_bytes(new_value)
            except Exception:
                self.log.error("Error loading public key from bytes")
                return False

            self.log.debug("Updating peer key for {peer} to {val}", peer=cnxn._peer, val=new_value)
            peer_state.info[PEER_KEY] = key
            self._maybe_register_contact(cnxn)
            self._maybe_do_routing_insert(cnxn)

        else:
            self.log.debug("Info update attempted for unrecognized key {key}", key=info_key)
            return False
        return True

    def _maybe_do_routing_insert(self, cnxn):
        info = cnxn.peer_state.info
        if LISTEN_PORT in info and PEER_KEY in info and ADDRS in info:
            contact = cnxn.peer_state.get_contact_info()
            for addr in info[ADDRS]:
                self.routing_table.insert(contact, addr)

    def _maybe_register_contact(self, cnxn):
        """
        Checks if we have enough peer info to register cnxn.peer_state in the
        peer tracker, and registers it if so.
        """
        peer_state = cnxn.peer_state
        if all(peer_state.info.get(key) for key in (LISTEN_PORT, PEER_KEY)):
            contact_info = peer_state.get_contact_info()
            try:
                self.peer_tracker.register_contact(contact_info, peer_state)
            except DuplicateContactError:
                self.log.warn("{peer} - DuplicateContactError registering contact info {info}", peer=cnxn._peer, info=contact_info)
                cnxn.transport.loseConnection()

    def get_info(self, key):
        """
        Gets local info. To get a remote peer's info, use `PeerState.get_info`.
        """

        # returns a Deferred in all cases. the Deferred may or may not come
        # pre-called.

        if key in DHTInfoKeys:
            key = key.value

        if key == MAX_VERSION.value:
            return succeed("n/a")  # no version yet
        if key == LISTEN_PORT.value:
            return succeed(self.listen_port)
        if key == PEER_KEY.value:
            return succeed(self.peer_key.public_bytes)
        if key == ADDRS.value:
            d = maybeDeferred(self.node_manager.get_addrs)
            d.addCallback(lambda result: [addr.as_bytes() for addr in result])
            return d

        # check plugins to see if any provide this info
        for provider in getPlugins(IInfoProvider):
            if key in provider.provided:
                # TODO log this plugin use
                return maybeDeferred(provider.get, key)

        return fail(UnsupportedInfoError())

    def do_lookup(self, addr, k=k):
        self.log.info("Setting up lookup for {a}", a=addr.hex())
        lookup = AddrLookup(self)
        lookup.configure(target=addr, num_peers=k)
        self._addr_lookups.append(lookup)

        def cb(val):
            self._addr_lookups.remove(lookup)
            return val

        d = lookup.start()
        d.addBoth(cb)
        self.stats_tracker.register_lookup(d, addr)
        return d

    def dht_get(self, key, redundancy=1):
        ...  # TODO

    def dht_put(self, key, value, redundancy=1, encoding='UTF-8'):
        ...  # TODO


class InfoPolicy:
    @staticmethod
    def addrs_valid(addrs, cnxn):
        if type(addrs) is not list:
            return False
        if len(addrs) > 0 and cnxn.transport is None:
            return False
        for addr in addrs:
            if type(addr) is not bytes:
                return False
            if len(addr) != 34:  # TODO don't hardcode this, make it a package-scoped constant or something
                return False
            if addr[4:8] != inet_aton(cnxn.transport.getPeer().host):
                return False
        return True

    @staticmethod
    def port_valid(port):
        if type(port) is not int:
            return False
        return 1024 <= port <= 65535
