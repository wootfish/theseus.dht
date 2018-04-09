from twisted.logger import Logger

from .enums import IDS


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

    def __init__(self, local_peer):
        self.local_peer = local_peer
        self.buckets = {(0, 2**160-1): set()}

    def __contains__(self, contact):
        for bucket in self.buckets.values():
            if contact in bucket:
                return True
            return False

    def _bucketLookup(self, node_address):
        addr_int = self.bytesToInt(node_address)
        for bucket in self.buckets:
            if bucket[0] <= addr_int <= bucket[1]:
                return bucket
        raise Exception("node_address out of bounds")

    def _bucketIsSplitCandidate(self, bucket):
        for node_id in self.local_peer.node_ids:
            if bucket[0] <= self.bytesToInt(node_id.node_id) <= bucket[1]:
                return True
        return False

    def _bucketSplit(self, bucket):
        # returns True if split was successful, False if it wasn't allowed
        if bucket[0] == bucket[1]:
            self.log.warn("Weird edge case encountered: Failed to split bucket {bucket}", bucket=bucket)
            return False

        if not self._bucketIsSplitCandidate(bucket):
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

    def insert(self, contact_info):
        """
        Retrieves the node IDs associated with contact_info and tries to insert
        contact_info to their associated buckets.
        """

        node_ids = self.getNodeIDs(contact_info)
        self.log.debug("Attempting to insert {contact} into routing table. (IDs: {node_ids})", contact=contact_info, node_ids=node_ids)

        for node_id in node_ids:
            self._insert(contact_info, node_id)

    def _insert(self, contact_info, node_id):
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

    def discard(self, contact_info):
        for bucket in self.buckets.values():
            if contact_info in bucket:
                bucket.remove(contact_info)

    def query(self, target_addr):
        return self.buckets[self._bucketLookup(target_addr)]

    def pretty(self):
        """
        Returns a prettyprintable representation of the table's state. This
        mostly means converting things to hex where appropriate and boiling off
        some boilerplate.
        """

        pretty = {}
        for bucket in self.table.buckets:
            lower_padded = "0x" + hex(bucket[0])[2:].rjust(40, '0')
            upper_padded = "0x" + hex(bucket[1])[2:].rjust(40, '0')

            key = "{}~{}".format(lower_padded, upper_padded)
            pretty[key] = []

            for node_addr, node_id in self.table.buckets[bucket].items():
                pretty_nodeid = "0x" + node_id.address.hex()
                pretty_ipaddr = node_addr.host + ":" + str(node_addr.port)
                pretty[key].append((pretty_nodeid, pretty_ipaddr))

            pretty[key].sort()  # lex ordering naturally sorts addrs ascending

        return pretty

    @staticmethod
    def getNodeIDs(contact_info):
        from app import peer
        node = peer.node_tracker.getByContact(contact_info)
        if node is None:
            RoutingTable.log.warn("Tried to get node IDs for {contact} but node_tracker has no corresponding record.", contact=contact_info)
            return []
        return node.getInfo(IDS)

    @staticmethod
    def bytesToInt(node_id):
        n = 0
        for byte in node_id:
            n <<= 8
            n += byte
        return n
