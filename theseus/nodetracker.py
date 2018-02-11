from twisted.internet import reactor
from twisted.internet.protocol import Factory

import time


class NodeState(Factory):
    reactor = reactor  # kind of wild how this isn't a no-op

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
        p = NoiseFactory(INITIATOR, Factory.forProtocol(DHTProtocol)).buildProtocol(addr)
        p.context = NoiseSettings(remote_static=self.info[NODE_KEY])
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


class NodeTracker:
    def __init__(self, parent):
        self.parent = parent

        self.by_cnxn = {}
        self.by_contact = {}

    def register(self, contact_info):
        if contact_info not in self.by_contact:
            new_state = NodeState.fromContact(contact_info)
            new_state.client_factory = self.client_factory
            self.by_contact[contact_info] = new_state
        return self.by_contact[contact_info]

    def getByCnxn(self, cnxn):
        return self.by_cnxn.get(cnxn)

    def getByContact(self, contact_info):
        return self.by_contact.get(contact)
