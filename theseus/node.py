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

    dispatcher = None
    listen_port = None
    node_key_private = None  # TODO: populate this field in startService
    node_key_public = None   # TODO: populate this field in startService

    _randrange = staticmethod(randrange)

    def __init__(self, manager, node_id=None):
        self.manager = manager
        self.node_id = node_id
        self.dispatcher = Dispatcher(self)

    def startService(self):
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
            port = self._randrange(*listen_port_range)
            if port in ports_to_avoid:
                continue

            self.log.info("Attempting to listen on port {port}...", port=port)

            try:
                self._listen(port)
            except CannotListenError:
                continue
            else:
                self.log.info("Now listening on port {port}.", port=port)
                break

        return port

    def _listen(self, port):
        # broken out so our node unit tests can override it to avoid touching the dispatcher
        self.dispatcher.listen(port)

    def updateID(self):
        self.node_id = NodeID()

        def callback(node_id):
            self.manager.table.refresh()
            return node_id

        self.node_id.on_id_hash.addCallback(callback)
