from twisted.internet import reactor
from twisted.internet.protocol import Factory

from .noisewrapper import NoiseWrapper, NoiseSettings
from .enums import INITIATOR

import time


class NodeState(Factory):
    reactor = reactor  # crazy how this isn't a no-op

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
    def fromCnxn(cls, cnxn):
        instance = cls()
        instance.role = RESPONDER
        instance.state = CONNECTING
        instance.host = cnxn.getHost()
        instance.cnxn = cnxn
        return instance

    def buildProtocol(self, addr):
        # TODO we need to figure out what the best way is for the NodeTracker
        # to find out about p here and add it to its self.by_cnxn dict
        # we'll need to either give this object a ref back to the tracker
        # or else move some factory duties to the tracker (which might be a
        # good idea anyway bc it's still sort of up in the air how we'll handle
        # _listening_)
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

        self.by_cnxn = {}
        self.by_contact = {}
        self.factory = WrappingFactory.forProtocol(NoiseWrapper, Factory.forProtocol(DHTProtocol))

    def buildProtocol(self, addr):
        p = self.factory.buildProtocol(addr)
        self.by_cnxn[p] = NodeState.fromCnxn(cnxn)
        return p

    def registerContact(self, contact_info):
        if contact_info not in self.by_contact:
            state = NodeState.fromContact(contact_info)
            state.tracker = self
            self.by_contact[contact_info] = state

        return self.by_contact[contact_info]

    def getByContact(self, contact_info):
        return self.by_contact.get(contact)

    def getByCnxn(self, cnxn):
        for state in self.by_contact.values():
            if state.cnxn is cnxn:
                return state
