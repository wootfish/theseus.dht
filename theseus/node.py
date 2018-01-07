from twisted.internet import reactor
from twisted.internet.error import CannotListenError
from twisted.application.service import Service
from twisted.logger import Logger

from .nodeid import NodeID
from .config import config

from random import randrange


class NodeService(Service):
    log = Logger()

    def __init__(self, manager, node_id=None):
        self.manager = manager

    def startService(self):
        self.updateID()
        self.startListening()

        self.dispatcher = Dispatcher(...)  # TODO

    def startListening(self):
        """
        Starts listening on a reasonable port. Sets self.listen_port to the
        port chosen.
        """

        # TODO: optionally take user-specified port, exit cleanly if port unavailable

        listen_port_range = config["listen_port_range"]
        ports_to_avoid = config["ports_to_avoid"]

        while True:
            listen_port = randrange(listen_port_range)

            if listen_port in ports_to_avoid:
                continue
            try:
                self._listen(listen_port)
            except CannotListenError:
                continue
            else:
                break

        return listen_port

    def _listen(self, port):
        self._listener = reactor.listenTCP(port, self.dispatcher)
