from twisted.logger import Logger

from typing import TYPE_CHECKING, Union, Tuple
if TYPE_CHECKING:
    from .nodeid import NodeID
    from .contactinfo import ContactInfo
    from .peer import PeerService


# TODO there are a lot of places where it's ambiguous whether a function takes
# a raw node ID (i.e. bytes) or a NodeID object, including several places where
# annotations might be wrong-- review, correct, and disambiguate!


class RoutingTable:
    """
    Maintains a Kademlia-style routing table.
    The actual entities stored are ContactInfo objects.
    The buckets storing these are determined by NodeIDs.
    A ContactInfo's NodeIDs are retrieved through RoutingTable.getNodeIDs.
    """

    log = Logger()
    k = 8

    def __init__(self, parent: "PeerService"):
        self.parent = parent
        self.buckets = {(0, 2**160-1): set()}

    def __contains__(self, contact: "ContactInfo"):
        for bucket in self.buckets.values():
            if contact in bucket:
                return True
            return False

    def _bucketLookup(self, node_address: bytes]):
        addr_int = self.bytesToInt(node_address)
        for bucket in self.buckets:
            if bucket[0] <= addr_int <= bucket[1]:
                return bucket

    def _bucketIsSplitCandidate(self, bucket: Tuple[int, int]):
        for node_id in self.parent.node_ids:
            if bucket[0] <= self.bytesToInt(node_id.node_id) <= bucket[1]:
                return True
        return False

    def _bucketSplit(self, bucket: Tuple[int, int]):
        # returns True if split was successful, False if it wasn't allowed
        if bucket[0] == bucket[1]:
            self.log.warn("Weird edge case encountered: Failed to split bucket {bucket}", bucket=bucket)
            return False

        if not _bucketIsSplitCandidate(bucket):
            return False

        bisector = (bucket[0] + bucket[1]) // 2
        lower = bucket[0], bisector
        upper = bisector+1, bucket[1]
        self.buckets[lower] = {}
        self.buckets[upper] = {}

        for listen_addr, node_id in self.buckets.pop(bucket).items():
            self._insert(listen_addr, node_id)

        self.log.info("Routing table bucket {bucket} split. Current table state: {pretty}", bucket=(hex(bucket[0]), hex(bucket[1])), pretty=self.pretty())
        return True

    def insert(self, contact_info: "ContactInfo"):
        """
        Retrieves the node IDs associated with contact_info and tries to insert
        contact_info to their associated buckets.
        """

        node_ids = self.getNodeIDs(contact_info)
        self.log.debug("Attempting to insert {contact} into routing table. (IDs: {node_ids})", contact=contact_info, node_ids=node_ids)

        for node_id in node_ids:
            self._insert(contact_info, node_id)

    def _insert(self, contact_info: "ContactInfo", node_id: bytes):
        bucket_key = self._bucketLookup(node_id)
        bucket = self.buckets[bucket_key]

        if contact_info in bucket:
            return

        if len(bucket) <= self.k:
            bucket.add(contact_info)
            return

        # bucket is full, but maybe we can split it & then retry the insert
        if self._bucketSplit(bucket_key):
            self._insert(contact_info, node_id)

    def discard(self, contact_info: "ContactInfo"):
        for bucket in self.buckets.values():
            if contact_info in bucket:
                bucket.remove(contact_info)

    def query(self, target_addr: bytes):
        return self.buckets[self._bucketLookup(target_addr)]

    @staticmethod
    def getNodeIDs(contact_info: "ContactInfo"):
        from app import peer
        node = peer.node_tracker.getByContact(contact_info)
        if node is None:
            self.log.warn("Tried to get node IDs for {contact} but node_tracker has no corresponding record.", contact=contact_info)
            return []
        return node.getInfo("ids")  # FIXME: what if getNodeIDs returns a Deferred?

    @staticmethod
    def bytesToInt(node_id: bytes):
        n = 0
        for byte in node_id:
            n <<= 8
            n += byte
        return n

    #@staticmethod
    #def xor(bytes_1: bytes, bytes_2: bytes):
    #    #if bytes_1 is None or bytes_2 is None:
    #    #    return float('inf')
    #    return RoutingTable.bytesToInt(bytes_1) ^ RoutingTable.bytesToInt(bytes_2)

    def pretty(self):
        """
        Returns a prettyprintable representation of the table's state. This
        mostly means converting things to hex where appropriate and boiling off
        some boilerplate.
        """

        pretty = {}
        for bucket in table.buckets:
            lower_padded = "0x" + hex(bucket[0])[2:].rjust(40, '0')
            upper_padded = "0x" + hex(bucket[1])[2:].rjust(40, '0')

            key = "{}~{}".format(lower_padded, upper_padded)
            pretty[key] = []

            for node_addr, node_id in table.buckets[bucket].items():
                pretty_nodeid = "0x" + node_id.address.hex()
                pretty_ipaddr = node_addr.host + ":" + str(node_addr.port)
                pretty[key].append((pretty_nodeid, pretty_ipaddr))

            pretty[key].sort()  # lex ordering naturally sorts addrs ascending

        return pretty
