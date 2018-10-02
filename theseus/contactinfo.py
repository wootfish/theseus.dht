from twisted.internet.address import IPv4Address

from noise.functions import KeyPair25519


class ContactInfo:
    def __init__(self, host, port, key):
        # host: str, currently expected to be IPv4 in dotted form

        # currently, key: KeyPair25519.from_public_bytes
        # in future, key: noise.functions._KeyPair subclass  (hopefully)

        # (key is not bytes because we don't want higher levels of abstraction
        # absorbing the complexity of having to know what public key algorithm
        # is in use -- _KeyPair can abstract this information away & provide a
        # consistent interface)

        if type(key) is bytes:
            key = KeyPair25519.from_public_bytes(key)

        self.host = host
        self.port = port
        self.key = key

    def __key(self):
        return (self.host, self.port, self.key.public_bytes)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__key() == other.__key()

    def __repr__(self):
        return "ContactInfo({}, {}, {})".format(*self.__key())

    def get_addr(self):
        return IPv4Address("TCP", self.host, self.port)
