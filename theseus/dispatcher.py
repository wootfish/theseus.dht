import time

from itertools import chain
from collections import deque

from twisted.logger import Logger
from twisted.internet import reactor
from twisted.internet.defer import Deferred, fail, succeed
from twisted.internet.error import TimeoutError
from twisted.internet.address import IPv4Address
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ClientEndpoint

from noise.functions import KeyPair25519

from .enums import ROLE, STATE, LAST_ACTIVE, INFO, CNXN, NODE_KEY
from .enums import INITIATOR, RESPONDER
from .enums import DISCONNECTED, CONNECTING
from .enums import ID, LISTEN_PORT, MAX_VERSION

from .noisewrapper import NoiseFactory
from .protocol import DHTProtocol
from .errors import TheseusConnectionError
from .config import config


class Dispatcher(Factory):
    log = Logger()

    blacklist_size = 500
    query_retries = 3
    query_retry_wait = 0.1

    def __init__(self, parent_node):
        self.clock = reactor  # so we can swap in a fake clock in tests

        self.node_key = parent_node.node_key

        self.manager = parent_node.manager
        self.routing_table = self.manager.table
        self.data_store = self.manager.data_store

        self.states = {}  # {IPv4addrs: {metadata keys: values}}
        self.unbound_states = {}  # like self.states but for cnxns where the remote cnxn port is ephemeral and the remote node's listen port is not known
        self.blacklist = deque(maxlen=self.blacklist_size)

        self.pending_info = {}  # {addrs: {metadata keys: [deferreds]}}
        self.active_lookups = []  # so we can check whether a node is part of any active lookups

        self.server_factory = NoiseFactory(self, RESPONDER)
        self.client_factory = NoiseFactory(self, INITIATOR)

        self._listeners = []

        self.info_getters = {
            MAX_VERSION: (lambda: config["listen_port"]),
            LISTEN_PORT: (lambda: parent_node.listen_port),
            ID: (lambda: parent_node.node_id.address),
            }
        self.info_setters = {
            MAX_VERSION: None,  # TODO
            LISTEN_PORT: self.maybeUpdateListenPort,
            ID: self.maybeUpdateNodeID,
            }

    def buildProtocol(self, addr):
        p = DHTProtocol()  # self.client_factory.buildProtocol(addr)
        p.info_getters = self.info_getters
        p.info_setters = self.info_setters
        p.routing_query = self.routing_table.query
        # TODO add refs to data store method(s) here once they're written

        if addr not in self.states:  # i.e. if this is an incoming, not outgoing, cnxn
            self.unbound_states[addr] = {
                    STATE: CONNECTING,
                    ROLE: RESPONDER,
                    INFO: {},
                    LAST_ACTIVE: time.monotonic(),
                    CNXN: p,
                    }

        return p

    def makeCnxn(self, addr, node_key, retries=0):
        if addr in self.blacklist:
            self.log.debug("Tried to connect to a blacklisted address: {addr}", addr=addr)
            return fail(TheseusConnectionError("Address blacklisted"))

        if addr in self.states and self.states[addr][STATE] is not DISCONNECTED:
            # redundant cnxn attempts shouldn't get made in the first place,
            # but might as well fail well by having them succeed after warning
            self.log.warn("Tried to add a redundant cnxn to address: {addr}", addr=addr)
            return succeed(self.states[CNXN])

        if node_key in set(node.node_key for node in self.manager):
            self.log.debug("Aborting cnxn to {addr} due to shared node key (?!)", addr=addr)
            return fail(TheseusConnectionError("Shared node key"))

        self.log.debug("Attempting to add new cnxn to {addr}", addr=addr)
        self.states[addr] = {
                STATE: CONNECTING,
                ROLE: INITIATOR,
                INFO: {},
                LAST_ACTIVE: time.monotonic(),
                CNXN: None,
                NODE_KEY: KeyPair25519.from_public_bytes(node_key),
                }

        def callback(cnxn):
            self.states[addr][CNXN] = cnxn
            return cnxn

        d = self._makeCnxn(addr)
        d.addCallback(callback)

        if retries > 0:
            d.addErrback(lambda _: self.makeCnxn(addr, retries-1))

        d.addErrback(lambda failure: failure.trap(TimeoutError))
        d.addErrback(lambda failure: self.addToBlacklist(addr, failure))
        return d

    def _makeCnxn(self, addr):
        # this is broken out so that tests can overwrite it to avoid touching
        # the network
        return TCP4ClientEndpoint(reactor, addr.host, addr.port).connect(self.client_factory)

    def listen(self, port):
        """
        Attempts to start listening for cnxns on the given port.
        Throws a CannotListenError if the port is not available.
        """
        listener = reactor.listenTCP(port, self.server_factory)
        self._listeners.append(listener)

    def sendQuery(self, addr, query_name, query_args, retries=0):
        if addr not in self.states or self.states[addr][CNXN] is None:
            self.log.debug("Tried to send query {query_name} to {addr}, but need to connect first. (args: {args})", query_name=query_name, addr=addr, args=query_args)
            d = self.makeCnxn(addr)
            d.addCallback(lambda cnxn: cnxn.sendQuery(query_name, query_args))

        elif self.states[addr][CNXN].connected:
            self.log.debug("Sending query {query_name} over existing cnxn to {addr} (args: {args])", query_name=query_name, addr=addr, args=query_args)
            d = self.states[addr][CNXN].sendQuery(query_name, query_args)

        else:
            self.log.debug("Retrying query {query_name} to {addr} in {retry} seconds.", query_name=query_name, addr=addr, retry=self.query_retry_wait)
            d = Deferred()
            d.addCallback(lambda _: self.sendQuery(addr, query_name, query_args))
            self.clock.callLater(self.query_retry_wait, d.callback, None)

        if retries > 0:
            d.addErrback(lambda _: self.sendQuery(addr, query_name, query_args, retries-1))

        return d

    def addToBlacklist(self, addr, reason=None):
        self.log.info("Blacklisting {addr} (reason: {reason})", addr=addr, reason=reason)
        self.blacklist.append(addr)

    # note to posterity: if looping through states and unbound_states to find a
    # cnxn turns out to be slow in these following functions, maybe consider
    # replacing states with some sort of bijective object, a double-dict of
    # some type that allows fast lookups from addr to cnxn _or_ cnxn to addr

    def maybeUpdateListenPort(self, cnxn, new_port):
        addr = next(addr for addr, _cnxn in self.states.items() if _cnxn is cnxn)
        new_addr = IPv4Address("TCP", addr.host, new_port)

        if new_addr == addr:
            return

        if new_addr in self.states:
            self.log.debug("Node at address {addr} tried to steal listen addr {new_addr}", addr=addr, new_addr=new_addr)
            raise Exception("Listen addr already claimed")

        state = self.unbound_states.pop(addr, None) or self.states.pop(addr)

        self.log.info("listen_port for cnxn on {addr} updated to {new_port}", addr=addr, new_port=new_port)
        self.states[new_addr] = state

    def maybeUpdateNodeID(self, cnxn, new_id):
        cnxn_addr, cnxn_state = None
        for addr, state in chain(self.states.items, self.unbound_states.items()):
            if cnxn is state[CNXN]:
                if state[INFO][ID] == new_id:
                    return  # node trying to "change" to its current id, for some reason
                cnxn_addr, cnxn_state = addr, state

            elif state[INFO][ID] == new_id:
                if cnxn_addr is None:
                    cnxn_addr = next(
                            _addr for _addr, _state
                            in chain(self.states.items, self.unbound_states.items())
                            if _state[CNXN] is cnxn
                            )

                self.log.debug("Node at address {addr} tried to steal ID {new_id}", addr=cnxn_addr, new_id=new_id)
                raise Exception("Node ID already claimed")

        if None in (cnxn_addr, cnxn_state):
            self.log.warn("Invariant violated: cnxn_addr, cnxn_state = {addr}, {state} for cnxn {cnxn}. This means this cnxn is not tracked by the Dispatcher, which shouldn't be possible!", addr=cnxn_addr, state=cnxn_state, cnxn=cnxn)
            raise Exception("Internal error")

        cnxn_state[INFO][ID] = new_id
        self.routing_table.remove(cnxn_addr)
        self.routing_table.insert(cnxn_addr, new_id)

    def getNodeInfo(self, addr, info_key, defer=True):
        if defer:
            ...
        else:
            state = self.states.get(addr) or self.unbound_states.get(addr, {})
            return state.get(INFO, {}).get(info_key)

    def getNodeKey(self, addr):
        return self.states.get(addr, {}).get(NODE_KEY)

    def getNodeState(self, addr, state_key):
        state = self.states.get(addr) or self.unbound_states.get(addr, {})
        return state.get(state_key)

    def announceIDUpdate(self):
        ...

    def findNodes(self, target_addr):
        ...
