from twisted.application.service import Service
from twisted.internet import reactor
from twisted.internet.defer import succeed, fail, maybeDeferred, DeferredList, Deferred
from twisted.internet.error import CannotListenError
from twisted.logger import Logger
from twisted.plugin import getPlugins

from noise.functions import DH, KeyPair25519

from .config import config
from .contactinfo import ContactInfo
from .enums import DHTInfoKeys, MAX_VERSION, LISTEN_PORT, PEER_KEY, ADDRS, LOW
from .errors import TheseusConnectionError, DuplicateContactError
from .nodeaddr import NodeAddress
from .peertracker import PeerTracker
from .plugins import IPeerSource, IInfoProvider
from .protocol import DHTProtocol
from .routing import RoutingTable
from .nodemanager import NodeManager
from .lookup import AddrLookup

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
    _addr_lookups = []  # type: List[Deferred]

    def __init__(self, num_nodes=5):
        super().__init__()

        self.node_addrs = []
        self.blacklist = deque(maxlen=self.blacklist_size)
        self.peer_key = self._generate_keypair()

        self.routing_table = RoutingTable()
        self.peer_tracker = PeerTracker(self)
        self.node_manager = NodeManager(num_nodes)
        self.node_manager.add_listener(self.on_addr_change)

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

    def stopService(self):
        super().stopService()
        # TODO are we allowed to return a deferred here to block on things like finishing up hash jobs?

    def on_addr_change(self, new_addrs):
        self.routing_table.reload(new_addrs)  # TODO pass in full list of eligible peers?
        # TODO should we advertise this info change? probably, right?

        # run lookups for all addresses
        for addr in new_addrs:
            d = self.do_lookup(addr.addr)
            self._addr_lookups.append(d)
            d.addCallback(lambda _: self._addr_lookups.remove(d))

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
            # check for formatting & uniqueness of all IDs, then assign
            if type(new_value) is not list:
                return False
            for addr in new_value:
                if type(addr) is not bytes:
                    break
                if len(addr) != 34:  # TODO don't hardcode this, make it a package-scoped constant or something
                    break
                if cnxn.transport is None or addr[4:8] != inet_aton(cnxn.transport.getPeer().host):
                    break
            else:
                self.log.debug("Node ID sanity checks passed.")
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
            self.log.debug("Node ID sanity checks failed.")
            return False

        elif info_key == LISTEN_PORT.value:
            if not (type(new_value) is int and 1024 <= new_value <= 65535):
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
            pass  # we'll only need this once we break backwards compatibility

        elif info_key == PEER_KEY.value:
            try:
                key = KeyPair25519.from_public_bytes(new_value)
            except Exception:
                return False
            self.log.debug("Updating {key} for {peer} to {val}", key=info_key, peer=cnxn._peer, val=new_value)
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

    def do_lookup(self, addr, k=8):  # TODO don't leave k hardcoded
        self.log.info("Setting up lookup for {addr}", addr=addr)
        lookup = AddrLookup(self)
        lookup.configure(target=addr, num_peers=k)
        return lookup.start()

    def dht_get(self, key, redundancy=1):
        ...  # TODO

    def dht_put(self, key, value, redundancy=1, encoding='UTF-8'):
        ...  # TODO
