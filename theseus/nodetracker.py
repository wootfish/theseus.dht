from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Factory, Protocol

from .noisewrapper import NoiseWrapper, NoiseSettings
from .enums import INITIATOR

import time
from typing import overload, TYPE_CHECKING

if TYPE_CHECKING:
    from .peer import PeerService
    from .contactinfo import ContactInfo
    from .bencode import BdecodeOutput


# FIXME: the annotations for several methods in this file should use structural typing -- can we get the appropriate Protocols (eg IAddressProtocol) from our type header files in here somehow?
# (maybe just copy over the relevant parts of _interfaces.py into a local file? it's janky b/c the two files could fall out of sync, but other than that it would work)


class NodeState(Factory):
    reactor = reactor  # kind of wild how this isn't a no-op

    state = None
    host = None
    cnxn = None
    #last_active = None

    def __init__(self) -> None:
        #self.last_active = time.monotonic()
        self.info = {}

    @classmethod
    def fromContact(cls, contact_info: "ContactInfo") -> "NodeState":
        instance = cls()
        instance.state = DISCONNECTED
        instance.host = contact_info.listen_addr.host
        instance.info[LISTEN_PORT] = contact_info.listen_addr.port
        instance.info[NODE_KEY] = contact_info.key
        return instance

    @classmethod
    def fromProto(cls, protocol: Protocol) -> "NodeState":
        instance = cls()
        instance.role = RESPONDER
        instance.state = CONNECTING
        instance.host = protocol.getHost()
        instance.cnxn = protocol
        return instance

    def buildProtocol(self, addr):  # FIXME: structural typing needed here (addr & return value)
        p = self.tracker.buildProtocol(addr)
        p.settings = NoiseSettings(INITIATOR, remote_static=self.info[NODE_KEY])
        return p

    def connect(self):  # FIXME structural typing needed here (return value)
        endpoint = TCP4ClientEndpoint(self.reactor, self.host, self.info[LISTEN_PORT])
        return endpoint.connect(self)

    def disconnect(self):
        ...

    def query(self, query_name: str, args: dict) -> Deferred:
        ...

    #@overload
    #def getInfo(self, info_key: str, allow_defered: None) -> "BdecodeOutput":
    #    pass
    #@overload
    #def getInfo(self, info_key: str, allow_deferred: bool) -> Union["BdecodeOutput", Deferred]:
    #    pass

    # NOTE: leaning on None rather than False for type hinting w/ the allowed_deferred param seems very jank
    # (because the type checker would wrongly think that passing allow_deferred=False could produce a Deferred return type)
    # is there a better way to do things?
    # and, can we get more specific with "BdecodeOutput" with return values?
    # (eg getInfo(info_key=ID, allow_deferred=False) should always return a (possibly-empty) List[bytes] -- can we annotate at this level of detail?)

    def getInfo(self, info_key, allow_deferred=None):
        ...

    def getContactInfo(self) -> "ContactInfo":
        ...


class NodeTracker(Factory):
    def __init__(self, parent: "PeerService") -> None:
        self.parent = parent

        self.addr_to_contact = {}
        self.contact_to_state = {}
        self.proto_to_state = {}

        self.factory = WrappingFactory.forProtocol(NoiseWrapper, Factory.forProtocol(DHTProtocol))

    def buildProtocol(self, addr):  # FIXME: structural subtyping needed here (addr & return value)
        p = self.factory.buildProtocol(addr)
        contact = self.addr_to_contact.get(addr)
        if contact is None:
            node_state = NodeState.fromProto(p)
        else:
            node_state = self.contact_to_state[contact]
        p.node_state = node_state
        self.proto_to_state[p] = node_state  # TODO once the dust settles, reconsider whether we need this & getByProto. we might not. it is nice in that it keeps references to all protocols we make, even ones we know nothing about the remote side of, but i'm not 100% convinced that's really necessary
        return p

    def registerContact(self, contact_info: "ContactInfo") -> "NodeState":
        if contact_info not in self.contact_to_state:
            state = NodeState.fromContact(contact_info)
            state.tracker = self
            self.contact_to_state[contact_info] = state

        return self.contact_to_state[contact_info]

    def getByContact(self, contact_info: "ContactInfo") -> "NodeState":
        return self.contact_to_state.get(contact)

    def getByProto(self, protocol) -> "NodeState":  # FIXME: structural subtyping needed here (protocol arg)
        return self.proto_to_state.get(protocol)
