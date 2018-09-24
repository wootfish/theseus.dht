from twisted.internet import reactor
from twisted.internet.defer import fail, succeed
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.protocol import Factory
from twisted.logger import Logger
from twisted.protocols.policies import WrappingFactory

from .contactinfo import ContactInfo
from .enums import DISCONNECTED, CONNECTING, CONNECTED
from .enums import INITIATOR, RESPONDER
from .enums import LISTEN_PORT, PEER_KEY
from .errors import RetriesExceededError, DuplicateContactError
from .noisewrapper import NoiseWrapper, NoiseSettings
from .protocol import DHTProtocol


class PeerState(Factory):
    log = Logger()

    cnxn = None
    host = None
    role = None
    state = None

    _endpoint_deferred = None
    _reactor = reactor

    def __init__(self):
        self.info = {}

    @classmethod
    def from_contact(cls, contact_info):
        PeerState.log.debug("Building new PeerState from contact: {contact}", contact=contact_info)
        instance = cls()
        instance.state = DISCONNECTED
        instance.host = contact_info.host
        instance.info[LISTEN_PORT] = contact_info.port
        instance.info[PEER_KEY] = contact_info.key
        return instance

    @classmethod
    def from_proto(cls, protocol):
        PeerState.log.debug("Building new PeerState from protocol: {proto}", proto=protocol)
        instance = cls()
        instance.state = CONNECTING
        instance.role = RESPONDER
        instance.cnxn = protocol
        return instance

    def buildProtocol(self, addr):
        if self.role is None or self.info.get(PEER_KEY) is None:
            return
        p = self.subfactory.buildProtocol(addr)
        p.settings = NoiseSettings.for_peer_state(self)
        return p

    def connect(self, reactor=None):
        reactor = reactor or self._reactor

        if self.state is not DISCONNECTED:
            return self._endpoint_deferred

        if not self.info.get(LISTEN_PORT):
            return fail(Exception("remote listen port unknown"))

        self.state = CONNECTING
        self.role = INITIATOR

        endpoint = TCP4ClientEndpoint(reactor, self.host, self.info[LISTEN_PORT])
        self._endpoint_deferred = endpoint.connect(self)
        self._endpoint_deferred.addCallback(lambda wrapper: wrapper.wrappedProtocol)
        return self._endpoint_deferred

    def onConnect(self, proto):
        # called by DHTProtocol
        self.state = CONNECTED
        self.cnxn = proto
        self.host = proto.transport.getPeer().host
        if self.role is INITIATOR:
            self.get_info()

    def disconnect(self):
        self.log.info("{peer} - Initiating disconnection", addr=self.cnxn.transport.getPeer())
        self.cnxn.transport.loseConnection()
        self.cnxn = None
        self._endpoint_deferred = None

    def query(self, query_name, args, retries=2):
        def errback(failure):
            if failure.check(RetriesExceededError):
                failure.raiseException()  # so we don't retry on errors that come from running out of retries
            return self.query(query_name, args, retries-1)

        if retries < 0:
            self.log.info("{peer} - {name} query failed (retries exceeded)", peer=self.cnxn.transport.getPeer(), name=query_name)
            return fail(RetriesExceededError())

        if self.cnxn is None:
            self.log.debug("Attempting to connect to {host}:{port} to send {name} query", host=self.host, port=self.info[LISTEN_PORT], name=query_name)
            d = self.connect()
            d.addCallback(lambda _: self.query(query_name, args, retries-1))
        else:
            d = self.cnxn.send_query(query_name, args)

        d.addErrback(errback)
        return d

    def get_contact_info(self):
        # note that there may not be a guarantee of LISTEN_PORT and PEER_KEY being populated
        return ContactInfo(self.host, self.info.get(LISTEN_PORT), self.info.get(PEER_KEY))

    def get_info(self, info_keys=None, advertise_keys=None, ignore_local=False):
        # info_keys should be a list of desired info keys
        # advertise should be a list of local keys to advertise (you do not need to provide values)
        # for both args, keys must be passed as bytes
        # if True, ignore_local forces a new request for all info keys rather
        # than locally looking up any that've already been requested

        # if info_keys and advertise are both None, they will both be assigned
        # sensible default values based on what we have and haven't talked to
        # this peer about so far

        # this function will always return a Deferred

        if info_keys is None:
            info_keys = tuple(DHTProtocol.supported_info_keys)

        if type(info_keys) not in (list, tuple) or not {str, bytes}.issuperset(set(type(key) for key in info_keys)):
            self.log.warn("Malformed info_keys argument to get_info. args: {a}, {b}, {c}", a=info_keys, b=advertise_keys, c=ignore_local)
            return fail(Exception("malformed info_keys argument"))

        def callback(advertise_dict):
            if type(advertise_dict) is not dict or not {str, bytes}.issuperset(set(type(key) for key in advertise_dict)):
                if advertise_dict is not None:
                    self.log.warn("Malformed advertise_dict argument in get_info callback. Advertise keys: {keys}", keys=advertise_keys)
                    self.log.debug("Full get_info arguments and advertise dict: {a}, {b}, {c}, {d}", a=info_keys, b=advertise_keys, c=ignore_local, d=advertise_dict)
                    return fail(Exception("malformed advertise_dict argument"))

            query = {"keys": info_keys}
            if advertise_dict:
                query["info"] = advertise_dict
            query_d = self.query("info", query)
            query_d.addCallback(lambda response: {
                key: response.get(b'info', {}).get(key) for key in info_keys
                })
            return query_d

        if info_keys is None and advertise_keys is None:
            deferred = self.cnxn.get_local_keys()
        elif advertise_keys is not None:
            deferred = self.cnxn.get_local_keys(advertise_keys)
        else:
            deferred = succeed(None)
        deferred.addCallback(callback)
        return deferred


class PeerTracker(Factory):
    """
    Responsible for maintaining a registry of PeerState instances corresponding
    to remote peers.
    """

    log = Logger()
    protocol = DHTProtocol

    def __init__(self, local_peer):
        self.local_peer = local_peer

        self.addr_to_contact = {}
        self.contact_to_state = {}

        self.subfactory = WrappingFactory.forProtocol(NoiseWrapper, Factory.forProtocol(self.protocol))

    def buildProtocol(self, addr):
        p = self.subfactory.buildProtocol(addr)
        contact = self.addr_to_contact.get((addr.host, addr.port))
        peer_state = self.contact_to_state.get(contact) or PeerState.from_proto(p.wrappedProtocol)
        p.wrappedProtocol.peer_state = peer_state
        p.wrappedProtocol.local_peer = self.local_peer
        return p

    def register_contact(self, contact_info, state=None):
        addr_tup = (contact_info.host, contact_info.port)
        if self.addr_to_contact.get(addr_tup, contact_info) != contact_info:
            self.log.warn("Tried to re-register {addr_tup} to {contact}", addr_tup=addr_tup, contact=contact_info)
            self.log.debug("new contact: {contact}   addr_to_contact: {val}", contact=contact_info, val=self.addr_to_contact)
            raise DuplicateContactError()

        self.addr_to_contact.setdefault(addr_tup, contact_info)
        if contact_info not in self.contact_to_state:
            self.log.debug("Registering contact {contact}", contact=contact_info)
            if state is None:
                state = PeerState.from_contact(contact_info)
                state.subfactory = self
            self.contact_to_state[contact_info] = state

        return self.contact_to_state[contact_info]

    def get(self, contact_info):
        return self.contact_to_state.get(contact_info)

    def get_from_addr(self, addr):
        if addr not in self.addr_to_contact:
            return
        return self.contact_to_state[self.addr_to_contact[addr]]
