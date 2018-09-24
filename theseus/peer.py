from twisted.application.service import Service
from twisted.internet import reactor
from twisted.internet.defer import succeed, fail, maybeDeferred
from twisted.internet.error import CannotListenError
from twisted.logger import Logger
from twisted.plugin import getPlugins

from noise.functions import DH, KeyPair25519

from .config import config
from .contactinfo import ContactInfo
from .enums import DHTInfoKeys, MAX_VERSION, LISTEN_PORT, PEER_KEY, ADDRS
from .errors import TheseusConnectionError, DuplicateContactError, UnsupportedInfoError
from .nodeaddr import NodeAddress
from .peertracker import PeerTracker
from .plugins import IPeerSource, IInfoProvider
from .protocol import DHTProtocol
from .routing import RoutingTable
from .nodemanager import NodeManager

from collections import deque
from random import randrange


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

    _randrange = randrange  # broken out for tests

    def __init__(self, num_nodes=5):
        super().__init__()

        self.node_addrs = []
        self.blacklist = deque(maxlen=self.blacklist_size)
        self.peer_key = self._generate_keypair()

        self.routing_table = RoutingTable()
        self.peer_tracker = PeerTracker(self)
        self.node_manager = NodeManager(num_nodes)

    def startService(self):
        super().startService()
        self.node_manager.start()
        self.listen_port = self._start_listening()

        for peer_source in getPlugins(IPeerSource):
            def cb(peers):
                self.log.info("Peers from {source}: {peers}", source=peer_source, peers=peers)
                for peer in peers:
                    try:
                        self.make_cnxn(peer)
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
            port = self._randrange(*listen_port_range)
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
        # TODO add logic to terminate any existing cnxns with blacklisted host
        self.blacklist.append(host)

    def make_cnxn(self, contact_info):
        if not self.running:
            return fail(TheseusConnectionError("Service must be running to make connections"))

        if contact_info.host in self.blacklist:
            return fail(TheseusConnectionError("Address blacklisted"))

        peer_state = self.peer_tracker.register_contact(contact_info)
        return peer_state.connect()

    def maybe_update_info(self, cnxn, info_key, new_value):
        # returns whether the info update succeeded (true) or failed (false)
        # update attempts on unrecognized keys always fail
        # redundant updates always succeed
        peer_state = cnxn.peer_state

        if info_key == ADDRS.value:
            # check for formatting & uniqueness of all IDs, then assign
            # question: how do we want to decide when to queue up ID checks?
            ...

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

        else:
            self.log.debug("Info update attempted for unrecognized key {key}", key=info_key)
            return False
        return True

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
        ...

    def dht_get(self, key, redundancy=1):
        ...  # TODO

    def dht_put(self, key, value, redundancy=1, encoding='UTF-8'):
        ...  # TODO
