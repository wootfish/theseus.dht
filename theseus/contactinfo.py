from twisted.internet.address import IPv4Address


class ContactInfo:
    def __init__(self, host, port, key):
        self.host = host
        self.port = port
        self.key = key

    def __key(self):
        return (self.host, self.port, self.key)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__key() == other.__key()

    def __repr__(self):
        return "ContactInfo({}, {}, {})".format(*self.__key())

    def as_bytes(self):
        ...  # TODO

    @classmethod
    def from_bytes(cls, bytestring):
        ...  # TODO

    def get_addr(self):
        return IPv4Address("TCP", self.host, self.port)
