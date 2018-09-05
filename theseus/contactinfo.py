from twisted.internet.address import IPv4Address


class ContactInfo:
    def __init__(self, host, port, key):
        self.host = host
        self.port = port
        self.key = key

    def __hash__(self):
        return hash((self.host, self.port, self.key))

    def __eq__(self, other):
        if other.__class__ is self.__class__:
            return (self.host, self.port, self.key) == (other.host, other.port, other.key)
        return NotImplemented

    def __repr__(self):
        return "ContactInfo({}, {}, {})".format(self.host, self.port, self.key)

    def as_bytes(self):
        ...  # TODO

    def get_addr(self):
        return IPv4Address("TCP", self.host, self.port)
