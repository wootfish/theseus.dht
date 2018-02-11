class ContactInfo:
    def __init__(self, remote_host, remote_port, remote_key=None, node_id=None):
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.key = remote_key
        self.node_id = node_id

    def __hash__(self):
        return hash((self.remote_host, self.remote_port, self.key, self.node_id))

    def __eq__(self, other):
        if not issubclass(other.__class__, ContactInfo):
            return False

        return (self.remote_host == other.remote_host and
                self.remote_port == other.remote_port and
                self.key == other.key and self.node_id == other.node_id)

    def __repr__(self):
        return "ContactInfo({}, {}, {})".format(self.addr, self.key, self.node_id)

    def asBytes(self):
        ...
