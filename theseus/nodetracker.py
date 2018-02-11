import time


class NodeState:
    role = None
    state = None
    host = None
    cnxn = None
    last_active = None
    info = {}

    def __init__(self):
        self.last_active = time.monotonic()

    @classmethod
    def asInitiator(cls, contact_info):
        instance = cls()
        instance.role = INITIATOR
        instance.state = DISCONNECTED
        instance.host = contact_info.listen_addr.host
        instance.info[LISTEN_PORT] = contact_info.listen_addr.port
        instance.info[NODE_KEY] = contact_info.key
        return instance

    @classmethod
    def asResponder(cls, cnxn):
        instance = cls()
        instance.role = RESPONDER
        instance.state = CONNECTING
        instance.host = cnxn.getHost()
        instance.cnxn = cnxn
        return instance

    def connect(self):
        ...

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

    def register(self, contact_info):
        ...

    def byCnxn(self, cnxn):
        ...

    def byContact(self, contact_info):
        ...
