from twisted.internet import reactor
from twisted.internet.error import CannotListenError
from twisted.internet.defer import Deferred, fail, DeferredList
from twisted.application.service import Service
from twisted.logger import Logger
from twisted.plugin import getPlugins

from noise.functions import DH

from random import randrange
from collections import deque

from .contactinfo import ContactInfo
from .nodeid import NodeID
from .config import config
from .nodetracker import NodeTracker
from .routing import RoutingTable
from .errors import TheseusConnectionError
from .plugins import IPeerSource

import sys


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

        DeferredList([node_id.on_id_hash for node_id in self.node_ids]).addCallback(
            lambda l: self.log.info("Local node IDs set: {ids}", ids=[t[1] for t in l])
            )

    def startService(self):
        super().startService()
        self.listen_port = self.startListening()

        self.log.info("PATH={path}", path=sys.path)
        for peer_source in getPlugins(IPeerSource):
            self.log.info("Loaded plugin for peer source {source}", source=peer_source)
            #peer_source.get().addCallback(lambda peers: self.log.info("Peers from {source}: {peers}", source=peer_source, peers=peers))
            peer_source.get().addCallback(lambda peers: list(map(self.makeCnxn, peers)))
            peer_source.put(ContactInfo(None, self.listen_port, self.peer_key))

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
        self.log.info("{foo}", foo=reactor.listenTCP)
        self.listener = reactor.listenTCP(port, self.node_tracker)

    def addToBlacklist(self, host):
        self.blacklist.append(host)

    def makeCnxn(self, contact_info):
        if not self.running:
            return fail(TheseusConnectionError("Service must be running to make connections"))

        if contact_info.host in self.blacklist:
            return fail(TheseusConnectionError("Address blacklisted"))

        node_state = self.node_tracker.registerContact(contact_info)
        return node_state.connect()

    def maybeUpdateInfo(self, cnxn, info_key, new_value):
        ...

    def doLookup(self, addr, tags):
        ...
