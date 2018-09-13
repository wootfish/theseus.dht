from twisted.logger import Logger

from .enums import ADDRS
from .constants import k, L


class RoutingTable:
    """
    Maintains a Kademlia-style routing table.
    The actual entities stored are ContactInfo objects.
    The buckets storing these are determined by NodeAddrs.
    A ContactInfo's NodeAddrs are retrieved through RoutingTable.get_node_addrs.
    """

    log = Logger()

    # rebind relevant constants so we can reference them as members of bound
    # methods' self namespace rather than the global namespace

    k = k
    L = L

    def __init__(self, local_peer):
        self.local_peer = local_peer
        self.buckets = {(0, 2**self.L - 1): set()}

    def __contains__(self, contact):
        for bucket in self.buckets.values():
            if contact in bucket:
                return True
            return False

    def _bucketLookup(self, node_address):
        addr_int = self.bytes_to_int(node_address)
        for bucket in self.buckets:
            if bucket[0] <= addr_int <= bucket[1]:
                return bucket
        raise Exception("node_address out of bounds")

    def _bucketIsSplitCandidate(self, bucket):
        for node_addr in self.local_peer.node_addrs:
            if bucket[0] <= self.bytes_to_int(node_addr.node_addr) <= bucket[1]:
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

        for listen_addr, node_addr in self.buckets.pop(bucket).items():
            self._insert(listen_addr, node_addr)

        self.log.info("Routing table bucket {bucket} split. Current table state: {pretty}", bucket=(hex(bucket[0]), hex(bucket[1])), pretty=self.pretty())
        return True

    def insert(self, contact_info):
        """
        Retrieves the node addrs associated with contact_info and tries to
        insert contact_info to their associated buckets.
        """

        node_addrs = self.get_node_addrs(contact_info)
        self.log.debug("Attempting to insert {contact} into routing table. (Addrs: {node_addrs})", contact=contact_info, node_addrs=node_addrs)

        for node_addr in node_addrs:
            self._insert(contact_info, node_addr)

    def _insert(self, contact_info, node_addr):
        bucket_key = self._bucketLookup(node_addr)
        bucket = self.buckets[bucket_key]

        if contact_info in bucket:
            return

        if len(bucket) <= self.k:
            bucket.add(contact_info)
            return

        # bucket is full, but maybe we can split it & then retry the insert
        if self._bucketSplit(bucket_key):
            self._insert(contact_info, node_addr)

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
            lower_padded = "0x" + hex(bucket[0])[2:].rjust(self.L//8, '0')
            upper_padded = "0x" + hex(bucket[1])[2:].rjust(self.L//8, '0')

            key = "{}~{}".format(lower_padded, upper_padded)
            pretty[key] = []

            for node_contact, node_addr in self.table.buckets[bucket].items():
                pretty_addr = "0x" + node_addr.addr.hex()
                pretty_ip = node_contact.host + ":" + str(node_contact.port)
                pretty[key].append((pretty_addr, pretty_ip))

            pretty[key].sort()  # lex ordering naturally sorts addrs ascending

        return pretty

    @staticmethod
    def get_node_addrs(contact_info):
        from app import peer
        peer = peer.peer_tracker.get(contact_info)
        if peer is None:
            RoutingTable.log.warn("Tried to get node addrs for {contact} but peer_tracker has no corresponding record.", contact=contact_info)
            return []
        return peer.get_info(ADDRS)

    @staticmethod
    def bytes_to_int(node_addr):
        n = 0
        for byte in node_addr:
            n <<= 8
            n += byte
        return n
