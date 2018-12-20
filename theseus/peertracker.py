from twisted.internet import reactor
from twisted.internet.defer import fail, succeed, inlineCallbacks, CancelledError
from twisted.internet.defer import TimeoutError as TwistedTimeoutError
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.protocol import Factory
from twisted.logger import Logger
from twisted.protocols.policies import WrappingFactory

from .contactinfo import ContactInfo
from .enums import DISCONNECTED, CONNECTING, CONNECTED
from .enums import INITIATOR, RESPONDER
from .enums import LISTEN_PORT, PEER_KEY
from .errors import QueryRetriesExceededError, DuplicateContactError
from .noisewrapper import NoiseWrapper, NoiseSettings
from .protocol import DHTProtocol


class PeerState(Factory):
    log = Logger()

    cnxn = None
    host = None
    role = None
    state = None

    query_timeout = 2  # seconds

    _endpoint_deferred = None

    _reactor = reactor
    _clock = reactor

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

    def connect(self):
        reactor = self._reactor

        if self.state is not DISCONNECTED:  # FIXME should this be "if self.state is CONNECTING"? and should we add more logic for other cases if so?
            return self._endpoint_deferred

        if not self.info.get(LISTEN_PORT):
            return fail(Exception("remote listen port unknown"))

        self.log.info("Attempting cnxn to {ip}:{port}", ip=self.host, port=self.info.get(LISTEN_PORT))
        self.state = CONNECTING
        self.role = INITIATOR

        endpoint = TCP4ClientEndpoint(reactor, self.host, self.info[LISTEN_PORT])
        self._endpoint_deferred = endpoint.connect(self)
        self._endpoint_deferred.addCallback(lambda wrapper: wrapper.wrappedProtocol)
        # TODO maybe add an errback for updating peer state on cnxn failure?
        return self._endpoint_deferred

    @inlineCallbacks
    def on_connect(self, proto):
        # called by DHTProtocol
        try:
            self.log.debug("{peer} - Updating state: connected", peer=proto.transport.getPeer())
            self.state = CONNECTED
            self.cnxn = proto
            self.host = proto.transport.getPeer().host
            if self.role is INITIATOR:
                # make an introduction
                self.log.debug("{peer} - Making introduction", peer=self.cnxn.transport.getPeer())
                info_keys = tuple(DHTProtocol.supported_info_keys)
                try:
                    local_info = yield self.cnxn.get_local_keys()
                except CancelledError:  # peer shut down while we were waiting for local keys
                    return
                self.query("info", {"keys": info_keys, "info": local_info}).addErrback(lambda _: None)  # best-effort introduction, ignore errors

        except Exception as e:
            self.log.failure("Unexpected error updating peer state")
            raise e

    def disconnect(self):
        self.log.info("{peer} - Initiating disconnection", peer=self.cnxn.transport.getPeer())
        self.cnxn.transport.loseConnection()

    def on_disconnect(self):
        self.cnxn = None
        self._endpoint_deferred = None

    def query(self, query_name, args, retries=2, timeout=None):
        clock = self._clock
        timeout = timeout or self.query_timeout

        def errback(failure):
            # retry, unless the error came from running out of retries or from cancellation
            if failure.check(QueryRetriesExceededError, CancelledError):
                self.log.debug("{peer} Query errback: Re-raising caught error {f}", peer=self.cnxn.transport.getPeer(), f=failure.getErrorMessage())
                failure.raiseException()
            self.log.debug("Errback on {name} query: {failure}. {n} retries left.", name=query_name, failure=failure.value, n=retries)
            return self.query(query_name, args, retries-1)

        def timeout_logger(failure):
            failure.trap(TwistedTimeoutError)
            self.log.debug("{peer} - {name} query timed out", peer=self.cnxn.transport.getPeer(), name=query_name)
            return failure

        if retries < 0:
            self.log.info("{peer} - {name} query failed (retries exceeded)", peer=self.cnxn.transport.getPeer(), name=query_name)
            return fail(QueryRetriesExceededError())

        if self.cnxn is None:
            self.log.debug("Attempting to connect to {host}:{port} to send {name} query", host=self.host, port=self.info[LISTEN_PORT], name=query_name)
            d = self.connect()
            d.addCallback(lambda _: self.query(query_name, args, retries-1))
        else:
            d = self.cnxn.send_query(query_name, args)

        d.addTimeout(timeout, clock)
        d.addErrback(timeout_logger)
        d.addErrback(errback)
        return d

    def get_contact_info(self):
        # note that there may not be a guarantee of LISTEN_PORT and PEER_KEY being populated
        # TODO: ^^^ is that comment, which was made a while ago, accurate? why
        # or why not? if it is accurate, we need ContactInfo.__key et al to
        # handle the case of those fields being None gracefully
        return ContactInfo(self.host, self.info.get(LISTEN_PORT), self.info.get(PEER_KEY))

    @inlineCallbacks
    def get_info(self, keys, ignore_cache=False):
        if ignore_cache:
            result = {}
        else:
            result = {key: self.info[key] for key in keys if key in self.info}

        todo = [key for key in keys if key not in result]
        if todo:
            answer = yield self.query("info", {"keys": todo})
            result.update(answer.get(b'info', {}))

        return result


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
            self.log.debug("new contact is {contact}; addr_to_contact is {val}", contact=contact_info, val=self.addr_to_contact)
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
