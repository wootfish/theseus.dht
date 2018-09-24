from twisted.logger import Logger

from .constants import k, L


class RoutingTable:
    log = Logger()

    k = k
    L = L

    class Entry:
        # TODO these need to be singletons (or to have an equality check based on their data field contents)
        def __init__(self, contact_info, node_addr):
            self.contact_info = contact_info
            self.node_addr = node_addr

        def __repr__(self):
            return "RoutingTable.Entry({}, {})".format(self.contact_info, self.node_addr)

    class Bucket:
        def __init__(self, lower, upper, k):
            self.lower = lower
            self.upper = upper
            self.k = k

            self.contents = []
            self.left_child = None
            self.right_child = None

        def insert(self, entry, local_addrs=None):
            # TODO if insert succeeds, add a timer to clean up the node ID when it expires
            # NOTE: returns True if insert succeeds _or_ entry is already in table

            local_addrs = [node_addr for node_addr in local_addrs or [] if self.covers(node_addr.addr)]

            if self.contents is None:
                # bucket is split
                if self.left_child.covers(entry.node_addr.addr):
                    return self.left_child.insert(entry, local_addrs)
                return self.right_child.insert(entry, local_addrs)

            if len(self.contents) < self.k:
                # bucket has room
                if entry not in self.contents:
                    self.contents.append(entry)
                RoutingTable.log.debug("Routing insert for {entry} succeeded.", entry=entry)
                return True

            if local_addrs:
                # bucket has no room, but can be split
                #print("Splitting bucket {} - {} due to node addrs {}".format(self.lower, self.upper, local_addrs))
                self.split()
                return self.insert(entry, local_addrs)

            RoutingTable.log.debug("Routing insert for {entry} failed.", entry=entry)
            return False

        def split(self):
            bisector = (self.lower + self.upper) // 2
            RoutingTable.log.debug("Splitting bucket 0x{low}~0x{high} into 0x{low}~0x{mid} and 0x{mid}~0x{high}", low=hex(self.lower), mid=hex(bisector), high=hex(self.upper))
            contents = self.contents
            self.contents = None
            self.left_child = RoutingTable.Bucket(self.lower, bisector, self.k)
            self.right_child = RoutingTable.Bucket(bisector + 1, self.upper, self.k)
            for entry in contents:
                self.insert(entry)

        def covers(self, addr: bytes):
            return self.lower <= RoutingTable.bytes_to_int(addr) <= self.upper

        def query(self, addr, lookup_size):
            addr_int = RoutingTable.bytes_to_int(addr)

            if self.contents:
                if len(self.contents) <= lookup_size:
                    return self.contents
                return sorted(
                        self.contents,
                        key=lambda entry: addr_int ^ RoutingTable.bytes_to_int(entry.node_addr.addr)
                        )[:lookup_size]

            if addr_int & (self.left_child.lower ^ self.right_child.lower):
                closer, further = self.right_child, self.left_child
            else:
                closer, further = self.left_child, self.right_child

            results = closer.query(addr, lookup_size)
            num_results = len(results)
            if num_results < lookup_size:
                results += further.query(addr, lookup_size - num_results)
            return results

        def get_contents(self):
            if self.contents:
                return self.contents
            return self.left_child.get_contents() + self.right_child.get_contents()

    def __init__(self, local_addrs=None):
        self.local_addrs = local_addrs or []
        self.root = self.Bucket(0, 2**self.L - 1, self.k)

    def query(self, addr, lookup_size=None):
        return self.root.query(addr, lookup_size or self.k)

    def insert(self, contact_info, node_addr):
        entry = self.Entry(contact_info, node_addr)
        self.log.debug("Attempting to insert {entry} into routing table.", entry=entry)
        return self.root.insert(entry, self.local_addrs)

    def reload(self, new_addrs=None, new_peers=None):
        # to be called after a local addr is replaced
        self.local_addrs = new_addrs or []

        contents = self.root.get_contents()  # TODO would there be any reason to shuffle this? just so that it's not predetermined which IDs from cut buckets survive? is there any good reason to want that, maybe security-related -- complicating any sort of malicious interference, etc?
        self.root = self.Bucket(0, 2**self.L - 1, self.k)
        for entry in contents:
            self.root.insert(entry, self.local_addrs)

        # TODO figure out how new_peers will be formatted. loop through values and (try to) insert them
        # (to support this, make sure that we gracefully handle attempted duplicate inserts)
        # this allows us to catch peers whose inserts were previously denied but which we might accept now
        for peer in new_peers or []:
            pass # TODO

    def _get_local_addrs(self):
        if self.local_peer is not None:
            return self.local_peer.node_addrs
        return []

    @staticmethod
    def bytes_to_int(bytestring):
        n = 0
        for byte in bytestring:
            n <<= 8
            n += byte
        return n
