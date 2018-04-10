from twisted.internet import reactor
from twisted.logger import Logger
from twisted.python.failure import Failure
from twisted.internet.defer import fail
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.protocol import Factory
from twisted.protocols.policies import WrappingFactory

from .enums import INITIATOR, RESPONDER
from .enums import DISCONNECTED, CONNECTING
from .enums import LISTEN_PORT, PEER_KEY
from .noisewrapper import NoiseWrapper, NoiseSettings
from .protocol import DHTProtocol


class NodeState(Factory):
    cnxn = None
    host = None
    state = None
    log = Logger()

    def __init__(self):
        self.info = {}

    @classmethod
    def fromContact(cls, contact_info):
        instance = cls()
        instance.state = DISCONNECTED
        instance.host = contact_info.host
        instance.info[LISTEN_PORT] = contact_info.port
        instance.info[PEER_KEY] = contact_info.key
        return instance

    @classmethod
    def fromProto(cls, protocol):
        instance = cls()
        instance.role = RESPONDER
        instance.state = CONNECTING
        instance.cnxn = protocol
        return instance

    def buildProtocol(self, addr):
        p = self.subfactory.buildProtocol(addr)
        p.settings = NoiseSettings(INITIATOR, remote_static=self.info[PEER_KEY])
        return p

    def connect(self, reactor=reactor):
        if not self.info.get(LISTEN_PORT):
            return fail(Exception("remote listen port unknown"))
        endpoint = TCP4ClientEndpoint(reactor, self.host, self.info[LISTEN_PORT])
        return endpoint.connect(self)

    def disconnect(self):
        self.log.info("Initiating disconnection from {addr}", addr=self.cnxn.getPeer())
        self.transport.loseConnection()
        self.cnxn = None

    def query(self, query_name, args, retries=2):
        if retries < 0:
            return fail(Exception("Retries exceeded"))
        if self.cnxn is None:
            return self.connect().addCallback(lambda _: self.query(query_name, args, retries-1))
        return self.cnxn.sendQuery(query_name, args).addErrback(
                lambda _: self.query(query_name, args, retries-1))

    def getContactInfo(self):
        ...

    def getInfo(self, info_keys, advertise=None, ignore_local=False):
        # info_keys should be a list of desired info keys
        # advertise should be a dict of local info keys: values
        # for both args, keys must be passed as bytes
        # if True, ignore_local forces a new request for all info keys rather
        # than locally looking up any that've already been requested

        # this function will always return a Deferred

        if type(info_keys) is not list or not {str, bytes}.issuperset(set(type(key) for key in info_keys)):
            self.log.warn("Malformed info_keys argument to getInfo. args: ({a}, {b}, {c})", a=info_keys, b=advertise, c=ignore_local)
            return fail(Exception("malformed info_keys argument"))
        if type(advertise) is not dict or not {str, bytes}.issuperset(set(type(key) for key in advertise)):
            self.log.warn("Malformed advertise argument to getInfo. args: ({a}, {b}, {c})", a=info_keys, b=advertise, c=ignore_local)
            if advertise is not None:
                return fail(Exception("malformed advertise argument"))

        query = {"keys": info_keys}
        if advertise:
            query["info"] = advertise
        return self.query("info", query).addCallback(lambda response: {
            key: response.get(b'info', {}).get(key) for key in info_keys
            })


class NodeTracker(Factory):
    log = Logger()

    def __init__(self, local_peer):
        self.local_peer = local_peer

        self.addr_to_contact = {}
        self.contact_to_state = {}

        self.subfactory = WrappingFactory.forProtocol(NoiseWrapper, Factory.forProtocol(DHTProtocol))

    def buildProtocol(self, addr):
        p = self.subfactory.buildProtocol(addr)
        contact = self.addr_to_contact.get(addr)
        if contact is None:
            node_state = NodeState.fromProto(p.wrappedProtocol)
        else:
            node_state = self.contact_to_state[contact]
        p.wrappedProtocol.node_state = node_state
        p.wrappedProtocol.local_peer = self.local_peer
        return p

    def registerContact(self, contact_info):
        if contact_info not in self.contact_to_state:
            self.log.debug("Registering contact {contact}", contact=contact_info)
            state = NodeState.fromContact(contact_info)
            state.subfactory = self
            self.contact_to_state[contact_info] = state

        return self.contact_to_state[contact_info]

    def get(self, contact_info):
        return self.contact_to_state.get(contact_info)
