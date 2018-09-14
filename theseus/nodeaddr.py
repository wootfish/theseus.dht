from twisted.internet.defer import inlineCallbacks

from .enums import CRITICAL, UNSET
from .hasher import hasher
from .constants import timeout_window
from .errors import ValidationError

from os import urandom
from time import time


class Preimage:
    # data class for hash preimages
    # TODO there has got to be a better way of making this a singleton class

    instances = {}

    def __init__(self, ts_bytes, ip_addr, entropy):
        self.ip_addr = ip_addr
        self.ts_bytes = ts_bytes
        self.entropy = entropy

    def __repr__(self):
        return "Preimage({}, {}, {})".format(self.ts_bytes, self.ip_addr, self.entropy)

    @classmethod
    def from_bytes(cls, preimage_bytes):
        # TODO validate length of preimage_bytes, warn/bail if not right
        if preimage_bytes not in cls.instances:
            ts_bytes = preimage_bytes[:4]
            ip_addr = preimage_bytes[4:8]
            entropy = preimage_bytes[8:14]
            cls.instances[preimage_bytes] = cls(ts_bytes, ip_addr, entropy)
        return cls.instances[preimage_bytes]

    def to_hash_inputs(self):
        return (self.ts_bytes + self.ip_addr, self.entropy+bytes(10))


class NodeAddress:
    timeout_window = timeout_window

    def __init__(self, addr, preimage, verified=True):
        self.addr = addr
        self.preimage = preimage
        self.verified = verified

    def __repr__(self):
        return "NodeAddress(({}, {}))".format(self.addr, self.preimage)

    @classmethod
    @inlineCallbacks
    def new(cls, ip_addr, priority=CRITICAL):
        preimage = Preimage(cls._ts_int_to_bytes(int(time())), ip_addr, urandom(6))
        image = yield hasher.do_hash(*preimage.to_hash_inputs(), priority)
        return cls(image, preimage)

    @classmethod
    @inlineCallbacks
    def from_preimage(cls, node_addr, preimage, trusted=False, priority=UNSET):
        ts = cls._ts_bytes_to_int(preimage.ts_bytes)

        if trusted:
            return cls(node_addr, preimage, verified=False)
        if not cls.check_timestamp(ts):
            raise ValidationError("Expired timestamp")

        image = yield hasher.do_hash(*preimage.to_hash_inputs(), priority)

        if False and 'the proof-of-work bytes are not valid':  # TODO
            raise ValidationError("Work factor not met")
        if False and 'the node address bytes are not valid':  # TODO
            raise ValidationError("Address does not match preimage")

        return cls(image, preimage, verified=True)

    @staticmethod
    def check_timestamp(ts, curr_time=None, timeout_window=None):
        timeout_window = timeout_window or NodeAddress.timeout_window
        curr_time = curr_time or time()
        return 0 <= curr_time - ts <= timeout_window

    @staticmethod
    def _ts_bytes_to_int(timestamp):
        n = 0
        for byte in timestamp:
            n = (n << 8) + byte
        return n

    @staticmethod
    def _ts_int_to_bytes(ts):
        bytestring = b''
        while ts > 0:
            bytestring = bytes([ts & 0xFF]) + bytestring
            ts >>= 8
        return bytestring
