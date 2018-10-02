from twisted.internet.defer import inlineCallbacks

from .enums import CRITICAL, UNSET
from .hasher import hasher
from .constants import timeout_window
from .errors import ValidationError

from os import urandom
from time import time
from socket import inet_aton

from typing import TYPE_CHECKING


class Preimage:
    def __init__(self, ts_bytes, ip_addr, entropy):
        if type(ip_addr) is str:
            ip_addr = inet_aton(ip_addr)

        self.ip_addr = ip_addr
        self.ts_bytes = ts_bytes
        self.entropy = entropy

    def __repr__(self):
        return "Preimage({}, {}, {})".format(self.ts_bytes, self.ip_addr, self.entropy)

    def as_bytes(self):
        """
        Returns a wire-friendly representation of the Preimage.
        """
        # ts (4 bytes), then ip (4 bytes), then entropy (6 bytes): 14 bytes total
        return self.ts_bytes + self.ip_addr + self.entropy

    def to_hash_inputs(self):
        return (self.ts_bytes + self.ip_addr, self.entropy+bytes(10))


class NodeAddress:
    timeout_window = timeout_window

    def __init__(self, addr, preimage, verified=True):
        self.addr = addr
        self.preimage = preimage
        self.verified = verified

    def __repr__(self):
        return "NodeAddress({}, {})".format(self.addr, self.preimage)

    def as_bytes(self):
        """
        Returns a wire-friendly representation of the NodeAddress.
        """
        #return b'ah fuck'  # TODO
        # preimage (14 bytes), then image (20 bytes, for now): 34 bytes total
        return self.preimage.as_bytes() + self.addr

    @classmethod
    @inlineCallbacks
    def new(cls, ip_addr, priority=CRITICAL):
        # allows passing in ip_addr as raw bytes or as a string in dotted form
        if type(ip_addr) is str:
            ip_addr = inet_aton(ip_addr)
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

    @classmethod
    def from_bytes(cls, addr_bytes, trusted=False, priority=UNSET):
        if len(addr_bytes) != 34:
            raise Exception("Wrong number of bytes for NodeAddr (should be 34)")

        ts_bytes, addr_bytes = addr_bytes[:4], addr_bytes[4:]
        ip_addr, addr_bytes = addr_bytes[:4], addr_bytes[4:]
        entropy, addr_bytes = addr_bytes[:6], addr_bytes[6:]

        preimage = Preimage(ts_bytes, ip_addr, entropy)
        return cls.from_preimage(addr_bytes, preimage, trusted, priority)

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
