from twisted.internet import reactor
from twisted.internet.protocol import Factory

from .noisewrapper import NoiseWrapper, NoiseSettings
from .enums import INITIATOR

import time


class NodeState(Factory):
    reactor = reactor  # kind of crazy how this isn't a no-op

    state = None
    host = None
    cnxn = None
    #last_active = None

    def __init__(self):
        #self.last_active = time.monotonic()
        self.info = {}

    @classmethod
    def fromContact(cls, contact_info):
        instance = cls()
        instance.state = DISCONNECTED
        instance.host = contact_info.listen_addr.host
        instance.info[LISTEN_PORT] = contact_info.listen_addr.port
        instance.info[NODE_KEY] = contact_info.key
        return instance

    @classmethod
    def fromProto(cls, protocol):
        instance = cls()
        instance.role = RESPONDER
        instance.state = CONNECTING
        instance.host = protocol.getHost()
        instance.cnxn = protocol
        return instance

    def buildProtocol(self, addr):
        p = self.tracker.buildProtocol(addr)
        p.settings = NoiseSettings(INITIATOR, remote_static=self.info[NODE_KEY])
        return p

    def connect(self):
        endpoint = TCP4ClientEndpoint(self.reactor, self.host, self.info[LISTEN_PORT])
        return endpoint.connect(self)

    def disconnect(self):
        ...

    def query(self, query_name, args):
        ...

    def getInfo(self, info_key):
        ...

    def getContactInfo(self):
        ...


class NodeTracker(Factory):
    def __init__(self, parent):
        self.parent = parent

        self.addr_to_contact = {}
        self.contact_to_state = {}
        self.proto_to_state = {}

        self.factory = WrappingFactory.forProtocol(NoiseWrapper, Factory.forProtocol(DHTProtocol))

    def buildProtocol(self, addr):
        p = self.factory.buildProtocol(addr)
        contact = self.addr_to_contact.get(addr)
        if contact is None:
            node_state = NodeState.fromProto(p)
        else:
            node_state = self.contact_to_state[contact]
        p.node_state = node_state
        self.proto_to_state[p] = node_state  # TODO once the dust settles, reconsider whether we need this & getByProto. we might not. it is nice in that it keeps references to all protocols we make, even ones we know nothing about the remote side of, but i'm not 100% convinced that's really necessary
        return p

    def registerContact(self, contact_info):
        if contact_info not in self.contact_to_state:
            state = NodeState.fromContact(contact_info)
            state.tracker = self
            self.contact_to_state[contact_info] = state

        return self.contact_to_state[contact_info]

    def getByContact(self, contact_info):
        return self.contact_to_state.get(contact)

    def getByProto(self, protocol):
        return self.proto_to_state.get(protocol)
