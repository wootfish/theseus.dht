class ContactInfo:
    def __init__(self, host, port, key):
        self.host = host
        self.port = port
        self.key = key

    def __hash__(self):
        return hash((self.host, self.port, self.key))

    def __eq__(self, other):
        if not issubclass(other.__class__, ContactInfo):
            return False

        return (self.host == other.host and self.port == other.host and self.key == other.key)

    def __repr__(self):
        return "ContactInfo({}, {}, {})".format(self.host, self.port, self.key)

    def asBytes(self):
        ...  # TODO
