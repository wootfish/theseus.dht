from twisted.internet.defer import Deferred

from .enums import CRITICAL, UNSET
from .hasher import hasher

from os import urandom
from time import time


class NodeID:
    def __init__(self, node_id=None, verify=True, priority=UNSET):
        # node_id=None generates a random ID with a current timestamp. If
        # node_id is None and priority is UNSET, priority is automatically
        # upgraded to CRITICAL.

        self.node_id = node_id
        self.will_verify = verify
        self.on_id_hash = Deferred()

        if node_id is None and priority is UNSET:
            self.priority = CRITICAL
        else:
            self.priority = priority

        self.on_id_hash = Deferred()

        if node_id is None:
            self.address = None
            self.preimage = None
            self.generate_address()

        elif verify:
            self.address = node_id[0]
            self.preimage = node_id[1]
            self.verify_address()

        else:
            self.address = node_id[0]
            self.preimage = None  # verify=False, so we might as well discard the preimage entirely
            self.on_id_hash.callback(True)

    def __repr__(self):
        address = None if self.address is None else hex(self.address)
        preimage = None if self.preimage is None else hex(self.preimage)
        return "NodeID(({}, {}))".format(address, preimage)

    def set_priority(self, new_priority):
        if new_priority.value > self.priority.value:
            self.priority = new_priority

            # re-submit the job w/ the new priority
            if self.node_id is None:
                self.generate_address()
            elif self.will_verify:
                self.verify_address()

    def generate_address(self):
        self.preimage = self.getHashInput()
        hasher.getNodeID(self.preimage, self.priority).chainDeferred(self.on_id_hash)

        def callback(node_id):
            self.address = node_id
            return node_id

        self.on_id_hash.addCallback(callback)

    def verify_address(self):
        hasher.checkNodeID(self.address, self.preimage, self.priority).chainDeferred(self.on_id_hash)

    @staticmethod
    def timestampIntToBytes(t):
        bytestring = b''
        while t > 0:
            bytestring = bytes([t & 0xFF]) + bytestring
            t >>= 8
        return bytestring

    @staticmethod
    def getHashInput():
        timestamp = NodeID.timestampIntToBytes(time())
        bytestring = urandom(6)
        return timestamp + bytestring
