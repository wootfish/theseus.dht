import time

from itertools import chain
from collections import deque, OrderedDict

from twisted.logger import Logger
from twisted.internet import reactor
from twisted.internet.defer import Deferred, fail, succeed
from twisted.internet.error import TimeoutError
from twisted.internet.address import IPv4Address
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ClientEndpoint

from .enums import ROLE, STATE, LAST_ACTIVE, INFO, CNXN
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

    def __init__(self, routing_table, data_store, parent_node):
        self.routing_table = routing_table
        self.data_store = data_store
        self.parent_node = parent_node

        self.clock = reactor  # so we can swap in a fake clock in tests

        self.states = {}  # {IPv4addrs: {metadata keys: values}}
        self.unbound_states = {}  # like self.states but for cnxns where the remote cnxn port is ephemeral and the remote node's listen port is not known
        self.blacklist = deque(maxlen=self.blacklist_size)

        self.pending_info = {}  # {addrs: {metadata keys: [deferreds]}}
        self.active_lookups = []  # so we can check whether a node is part of any active lookups

        self.client_factory = NoiseFactory(self, INITIATOR)
        self.server_factory = NoiseFactory(self, RESPONDER)

        self.info_getters = {
            MAX_VERSION: (lambda: config["listen_port"]),
            LISTEN_PORT: (lambda: self.parent_node.listen_port),
            ID: (lambda: self.parent_node.node_id),
            }
        self.info_updaters = {
            MAX_VERSION: None,  # TODO
            LISTEN_PORT: self.maybeUpdateListenPort,
            ID: self.maybeUpdateNodeID,
            }

    def buildProtocol(self, remote):
        addr = remote.getHost()

        if addr in self.states or addr in self.unbound_states:
            self.log.warn("Tried to build redundant cnxn protocol for address {addr}", addr=addr)
            return  # aborts the cnxn

        p = DHTProtocol()
        p.find, p.onFind = self.routing_table.getCallbacks()
        p.get, p.put, p.onGet = self.data_store.getCallbacks()
        p.info, p.onInfo = self.getCallbacks(addr)

        if addr not in self.states:
            self.unbound_states[addr] = {
                    STATE: CONNECTING,
                    ROLE: RESPONDER,
                    INFO: {},
                    LAST_ACTIVE: time.monotonic(),
                    CNXN: p,
                    }

        return p

    def getCallbacks(self, addr):
        data_names = OrderedDict((
            (b'max_version', MAX_VERSION),
            (b'listen_port', LISTEN_PORT),
            (b'id', ID),
            ))

        def info_response_callback(args):
            assert type(args) is dict

            info = args.get(b'info', {})
            for str_key, enum_key in data_names.items():
                if str_key in info:
                    self.info_updaters[enum_key](addr, info[str_key])

        def info_query_callback(args):
            info_response_callback(args)

            info = {}
            for key in args.get(b'keys', []):
                if data_names[key] in self.info_getters:
                    info[key] = self.info_getters(data_names[key])

            return {b'info': info}

        return info_query_callback, info_response_callback

    def makeCnxn(self, addr, retries=0):
        if addr in self.blacklist:
            self.log.debug("Tried to connect to a blacklisted address: {addr}", addr=addr)
            return fail(TheseusConnectionError("Address blacklisted"))

        if addr in self.states and self.states[addr][STATE] is not DISCONNECTED:
            self.log.warn("Tried to add a redundant cnxn to address: {addr}", addr=addr)
            return fail(TheseusConnectionError("Redundant cnxn"))  # or should we 'fail gently' by returning succeed(self.states[CNXN])?  TODO: decide

        if addr[1] in set(node.listen_port for node in self.parent_node.manager):
            self.log.debug("Aborting cnxn to {addr} due to shared listen port", addr=addr)
            return fail(TheseusConnectionError("Shared listen port"))

        self.log.debug("Attempting to add new cnxn to {addr}", addr=addr)
        self.states[addr] = {
                STATE: CONNECTING,
                ROLE: INITIATOR,
                INFO: {},
                LAST_ACTIVE: time.monotonic(),
                CNXN: None,
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
        return TCP4ClientEndpoint(reactor, *addr).connect(self)

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

    def maybeUpdateListenPort(self, addr, new_port):
        new_addr = IPv4Address("TCP", addr.host, new_port)

        if new_addr == addr:
            # no change
            return

        if new_addr in self.states:
            self.log.debug("Node at address {addr} tried to steal listen addr {new_addr}", addr=addr, new_addr=new_addr)
            raise Exception("Listen addr already claimed")

        if addr in self.unbound_states:
            state = self.unbound_states.pop(addr)
        else:
            state = self.states.pop(addr)

        self.log.info("listen_port for cnxn on {addr} updated to {new_port}", addr=addr, new_port=new_port)
        self.states[new_addr] = state

        # update callbacks for new address
        state[CNXN].info, state[CNXN].onInfo = self.getCallbacks(new_addr)

    def maybeUpdateNodeID(self, addr, new_id):
        for node_addr, node_state in chain(self.states.items(), self.unbound_states.items()):
            if node_addr == addr:
                if node_state[INFO][ID] == new_id:
                    return
                continue

            if node_state[INFO][ID] == new_id:
                self.log.debug("Node at address {addr} tried to steal ID {new_id}", addr=addr, new_id=new_id)
                raise Exception("Node ID already claimed")

        self.states.get(addr, self.unbound_states.get(addr))[INFO][ID] = new_id

        self.routing_table.remove(addr)
        self.routing_table.insert(addr, new_id)

    def getNodeInfo(self, addr, info_key, defer=True):
        if defer:
            ...
        else:
            state = self.states.get(addr) or self.unbound_states.get(addr, {})
            return state.get(INFO, {}).get(info_key)

    def getNodeState(self, addr, state_key):
        state = self.states.get(addr) or self.unbound_states.get(addr, {})
        return state.get(state_key)

    def announceIDUpdate(self):
        ...

    def findNodes(self, target_addr):
        ...
