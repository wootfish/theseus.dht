from twisted.internet import reactor
from twisted.internet.error import CannotListenError
from twisted.application.service import Service
from twisted.logger import Logger

from .nodeid import NodeID
from .config import config
from .dispatcher import Dispatcher

from random import randrange


class NodeService(Service):
    log = Logger()

    listen_port = None

    def __init__(self, manager, node_id=None):
        self.manager = manager
        self.node_id = node_id

    def startService(self):
        #self.dispatcher = Dispatcher(...)  # TODO

        self.updateID()
        self.listen_port = self.startListening()

    def startListening(self):
        """
        Starts listening on a reasonable port.
        """

        # TODO: optionally take user-specified port, exit cleanly if port unavailable

        listen_port_range = config["listen_port_range"]
        ports_to_avoid = config["ports_to_avoid"]

        while True:
            listen_port = randrange(*listen_port_range)
            if listen_port in ports_to_avoid:
                continue

            self.log.info("Attempting to listen on port {port}...", port=listen_port)

            try:
                self._listen(listen_port)
            except CannotListenError:
                continue
            else:
                self.log.info("Now listening on port {port}.", port=listen_port)
                break

        return listen_port

    def updateID(self):
        self.node_id = NodeID()

        def callback(node_id):
            self.manager.table.refresh()
            return node_id

        self.node_id.on_id_hash.addCallback(callback)

    def _listen(self, port):
        self._listener = reactor.listenTCP(port, self.dispatcher)
