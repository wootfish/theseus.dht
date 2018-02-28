from twisted.internet.error import CannotListenError
from twisted.application.service import Service
from twisted.logger import Logger

from noise.functions import DH

from random import randrange

from .nodeid import NodeID
from .config import config
from .nodetracker import NodeTracker


class PeerService(Service):
    log = Logger()
    listener = None

    blacklist_size = 500

    _randrange = randrange  # broken out for tests

    def __init__(self, num_nodes=5):
        super().__init__()

        self.node_ids = [NodeID() for _ in range(num_nodes)]
        self.peer_key = DH("ed25519").generate_keypair()

        self.routing_table = RoutingTable(self)
        self.node_tracker = NodeTracker(self)

        self.blacklist = deque(maxlen=self.blacklist_size)
        self.pending_cnxns = []

    def startService(self):
        self.listen_port = self.startListening()

        while self.pending_cnxns:
            contact, d = self.pending_cnxns.pop()
            self.makeCnxn(contact).chainDeferred(d)

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
                self.log.info("Now listening on port {port} with node key {key}", port=port, key=self.node_key.public_bytes)
                break

        return port

    def _listen(self, port):
        """
        Attempts to start listening for cnxns on the given port.
        Throws a CannotListenError if the port is not available.
        """
        self.listener = reactor.listenTCP(port, self.node_tracker)

    def makeCnxn(self, contact_info):
        if not self.running:
            d = Deferred()
            self.pending_cnxns.append((contact_info, d))
            return d

        if listen_addr.host in self.blacklist:
            return fail(TheseusConnectionError("Address blacklisted"))

        node_state = self.node_tracker.registerContact(contact_info)
        return node_state.connect()

    def maybeUpdateInfo(self, cnxn, info_key, new_value):
        ...

    def doLookup(self, addr, tags):
        ...
