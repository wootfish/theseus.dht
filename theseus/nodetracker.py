from twisted.internet import reactor
from twisted.logger import Logger
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

    def query(self, query_name, args):
        ...

    def getContactInfo(self):
        ...

    def getInfo(self, info_keys, advertise=None, ignore_local=False):
        # TODO
        # info_keys should be a list of desired info keys
        # advertise should be a dict of local info keys: values
        # for both args, keys may be passed either as bytes or as NodeInfoKeys enum members
        # if True, ignore_local forces a new request for all info keys rather than locally looking up any that've already been requested
        # this function will always return a Deferred
        ...


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
            node_state = NodeState.fromProto(p)
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

    def getByContact(self, contact_info):
        return self.contact_to_state.get(contact_info)
