from twisted.internet.defer import Deferred

from .enums import CRITICAL, UNSET
from .hasher import hasher

from os import urandom
from time import time


class NodeID:
    def __init__(self, node_id=None, id_preimage=None, verify=True, priority=UNSET):
        """
        node_id==None, id_preimage==None generates a random ID with a current
        timestamp.

        node_id==None, id_preimage!=None hashes a given input and sets node_id
        to the output.

        node_id!=None, id_preimage==None raises an error unless verify=False

        node_id!=None, id_preimage!=None verifies that the given ID and
        preimage match, unless verify=False

        If node_id is None and priority is UNSET, priority is automatically
        upgraded to CRITICAL.
        """

        self.node_id = node_id
        self.will_verify = verify
        self.on_id_hash = Deferred()

        if node_id is None and priority is UNSET:
            self.priority = CRITICAL
        else:
            self.priority = priority

        self.address = node_id
        self.preimage = id_preimage
        self.on_id_hash = Deferred()

        if node_id is None:
            self.generate_address()

        elif verify:
            if id_preimage is None:
                raise Exception("No hash preimage to verify node ID against")
            else:
                self.verify_address()

        else:
            self.preimage = None  # verify is False, so we might as well discard the preimage entirely
            self.on_id_hash.callback(True)

    def __repr__(self):
        #address = None if self.address is None else hex(self.address)
        #preimage = None if self.preimage is None else hex(self.preimage)
        return "NodeID(({}, {}))".format(self.address, self.preimage)

    def set_priority(self, new_priority):
        if new_priority.value > self.priority.value:
            self.priority = new_priority

            # re-submit the job w/ the new priority
            if self.node_id is None:
                self.generate_address()
            elif self.will_verify:
                self.verify_address()

    def generate_address(self, preimage=None):
        self.preimage = self.preimage or self._get_hash_input()

        def callback(node_id):
            self.address = node_id
            return node_id

        self.on_id_hash.addCallback(callback)
        hasher.get_node_ID(self.preimage, self.priority).chainDeferred(self.on_id_hash)

    def verify_address(self):
        hasher.check_node_ID(self.address, self.preimage, self.priority).chainDeferred(self.on_id_hash)

    @staticmethod
    def _ts_int_to_bytes(t):
        bytestring = b''
        while t > 0:
            bytestring = bytes([t & 0xFF]) + bytestring
            t >>= 8
        return bytestring

    @staticmethod
    def _get_hash_input():
        timestamp = NodeID._ts_int_to_bytes(int(time()))
        bytestring = urandom(6)
        return timestamp + bytestring
