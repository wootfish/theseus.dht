from twisted.internet import reactor
from twisted.internet.error import CannotListenError
from twisted.internet.defer import succeed, fail, DeferredList
from twisted.application.service import Service
from twisted.logger import Logger
from twisted.plugin import getPlugins

from noise.functions import DH, KeyPair25519

from random import randrange
from collections import deque

from .protocol import DHTProtocol
from .contactinfo import ContactInfo
from .nodeid import NodeID
from .config import config
from .peertracker import PeerTracker
from .routing import RoutingTable
from .errors import TheseusConnectionError, DuplicateContactError
from .plugins import IPeerSource, IInfoProvider
from .enums import NodeInfoKeys, MAX_VERSION, LISTEN_PORT, PEER_KEY, IDS


class PeerService(Service):
    log = Logger()
    listener = None

    blacklist_size = 500

    _randrange = randrange  # broken out for tests
    _ids_deferred = None

    def __init__(self, num_nodes=8):
        super().__init__()

        self.node_ids = [NodeID() for _ in range(num_nodes)]
        self.peer_key = DH("ed25519").generate_keypair()

        self.routing_table = RoutingTable(self)
        self.peer_tracker = PeerTracker(self)

        self.blacklist = deque(maxlen=self.blacklist_size)

        def callback(dl_result):
            ids = [t[1] for t in dl_result]
            self.log.info("Local node IDs set: {ids}", ids=[node_id.hex() for node_id in ids])
            return ids

        self._ids_deferred = DeferredList([node_id.on_id_hash for node_id in self.node_ids])
        self._ids_deferred.addCallback(callback)

    def startService(self):
        super().startService()
        self.listen_port = self.startListening()

        for peer_source in getPlugins(IPeerSource):
            def cb(peers):
                self.log.info("Peers from {source}: {peers}", source=peer_source, peers=peers)
                for peer in peers:
                    try:
                        self.makeCnxn(peer)
                    except DuplicateContactError:
                        self.log.warn("Differing contact info records encountered for {host}:{port}", host=peer.host, port=peer.port)

            self.log.info("Loading plugin for peer source {source}", source=peer_source)
            peer_source.get().addCallback(cb)
            peer_source.put(ContactInfo(None, self.listen_port, self.peer_key))

        for info_provider in getPlugins(IInfoProvider):
            DHTProtocol.supported_info_keys.update(info_provider.provided)

    def startListening(self):
        """
        Starts listening on a reasonable port.
        """

        # maybe we should add the option to take a user-specified port (and exit cleanly if it's not available)?

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
        """
        self.listener = reactor.listenTCP(port, self.peer_tracker)

    def addToBlacklist(self, host):
        self.blacklist.append(host)

    def makeCnxn(self, contact_info):
        if not self.running:
            return fail(TheseusConnectionError("Service must be running to make connections"))

        if contact_info.host in self.blacklist:
            return fail(TheseusConnectionError("Address blacklisted"))

        peer_state = self.peer_tracker.registerContact(contact_info)
        return peer_state.connect()

    def maybeUpdateInfo(self, cnxn, info_key, new_value):
        # returns whether the info update succeeded (true) or failed (false)
        # update attempts on unrecognized keys always fail
        # redundant updates always succeed
        peer_state = cnxn.peer_state

        if info_key == IDS.value:
            # check for formatting & uniqueness of all IDs, then set
            # how do we want to decide when to queue up ID checks?
            ...

        elif info_key == LISTEN_PORT.value:
            if not (type(new_value) is int and 1024 <= new_value <= 65535):
                return False
            addr = peer_state.host, peer_state.info.get(LISTEN_PORT)
            if (self.peer_tracker.getFromAddr(addr) or peer_state) != peer_state:
                self.log.warn("{peer} - Tried to steal listen addr {addr}!", peer=cnxn._peer, addr=addr)
                cnxn.transport.loseConnection()
                return False
            peer_state.info[LISTEN_PORT] = new_value
            self._maybeRegisterContact(cnxn)

        elif info_key == MAX_VERSION.value:
            pass  # we'll only need this once we break backwards compatibility

        elif info_key == PEER_KEY.value:
            try:
                key = KeyPair25519.from_public_bytes(new_value)
            except Exception:
                return False
            self.log.debug("Updating {key} for {peer} to {val}", key=info_key, peer=cnxn._peer, val=new_value)
            peer_state.info[PEER_KEY] = key
            self._maybeRegisterContact(cnxn)

        else:
            return False
        return True

    def _maybeRegisterContact(self, cnxn):
        peer_state = cnxn.peer_state
        if all(peer_state.info.get(key) for key in (LISTEN_PORT, PEER_KEY)):
            contact_info = peer_state.getContactInfo()
            try:
                self.peer_tracker.registerContact(contact_info, cnxn.peer_state)
            except DuplicateContactError:
                self.log.warn("{peer} - DuplicateContactError registering contact info {info}", peer=cnxn._peer, info=contact_info)
                cnxn.transport.loseConnection()
                return False

    def getInfo(self, key):
        # returns a Deferred in all cases. the Deferred may or may not come
        # pre-called.

        if key in NodeInfoKeys:
            key = key.value

        if key == MAX_VERSION.value:
            return succeed("n/a")  # no version yet
        if key == LISTEN_PORT.value:
            return succeed(self.listen_port)
        if key == PEER_KEY.value:
            return succeed(self.peer_key.public_bytes)
        if key == IDS.value:
            return self._ids_deferred

        for provider in getPlugins(IInfoProvider):
            if key in provider.provided:
                return succeed(provider.get(key))

    def doLookup(self, addr, tags):
        ...
