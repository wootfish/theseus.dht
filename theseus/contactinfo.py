from twisted.internet.address import IPv4Address

class ContactInfo:
    def __init__(self, listen_addr, remote_key, node_id):
        self.listen_addr = listen_addr
        self.key = remote_key
        self.node_id = node_id

    def __hash__(self):
        return hash((self.addr, self.key, self.node_id))

    def __eq__(self, other):
        if not issubclass(other.__class__, ContactInfo):
            return False

        return self.node_id == other.node_id and self.addr == other.addr and self.key == other.key

    def __repr__(self):
        return "ContactInfo({}, {}, {})".format(self.addr, self.key, self.node_id)

    def asBytes(self):
        ...
