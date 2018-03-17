from twisted.internet.address import IPv4Address, IPv6Address

from typing import Union, Any


class ContactInfo:
    def __init__(self, host: Union[IPv4Address, IPv6Address], port: int, key):  # TODO what type should 'key' be? is it bytes?
        self.host = host
        self.port = port
        self.key = key

    def __hash__(self):
        return hash((self.host, self.port, self.key))

    def __eq__(self, other: Any):
        if not issubclass(other.__class__, ContactInfo):
            return False

        return (self.host == other.host and self.port == other.host and self.key == other.key)

    def __repr__(self):
        return "ContactInfo({}, {}, {})".format(self.host, self.port, self.key)

    def asBytes(self):
        ...  # TODO
