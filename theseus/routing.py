from twisted.logger import Logger
from twisted.internet.defer import inlineCallbacks

from .constants import k, L
from .nodeaddr import NodeAddress
from .contactinfo import ContactInfo
from .enums import UNSET

from random import SystemRandom
from socket import inet_ntoa


class RoutingEntry:
    def __init__(self, contact_info, node_addr):
        self.contact_info = contact_info
        self.node_addr = node_addr

    def __repr__(self):
        return "RoutingEntry({}, {})".format(self.contact_info, self.node_addr)

    def __key(self):
        contact_key = (self.contact_info.host, self.contact_info.port, self.contact_info.key)
        node_key = (self.node_addr.addr, self.node_addr.preimage)
        return contact_key + node_key

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.__key() == self.__key()

    def __hash__(self):
        return hash(self.__key())

    def as_bytes(self):
        # address (34 bytes), then port (2 bytes), then key (32 bytes): 68 bytes (!)
        port = self.contact_info.port
        port_bytes = bytes([port >> 8, port & 0xFF])
        return self.node_addr.as_bytes() + port_bytes + self.contact_info.key.public_bytes

    @classmethod
    @inlineCallbacks
    def from_bytes(cls, bytestring, trusted=False, priority=UNSET):
        # address (34 bytes), then port (2 bytes), then key (32 bytes): 68 bytes (!)
        if len(bytestring) != 68:
            raise Exception("wrong number of bytes for RoutingEntry (68 expected)")

        addr_bytes, port_bytes, key_bytes = bytestring[:34], bytestring[34:36], bytestring[36:]
        address = yield NodeAddress.from_bytes(addr_bytes, trusted, priority)

        ip = inet_ntoa(address.preimage.ip_addr)
        port = (port_bytes[0] << 8) + port_bytes[1]
        contact = ContactInfo(ip, port, key_bytes)

        return cls(contact, address)


class RoutingTable:
    log = Logger()

    k = k
    L = L

    _rng = SystemRandom()

    class Bucket:
        def __init__(self, lower, upper, k):
            self.lower = lower
            self.upper = upper
            self.k = k

            self.contents = []
            self.left_child = None
            self.right_child = None

        def insert(self, entry, local_addrs=None, quiet=False):
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
                if not quiet:
                    RoutingTable.log.debug("Routing insert succeeded for {entry}", entry=entry)
                return True

            if local_addrs:
                # bucket has no room, but can be split
                #print("Splitting bucket {} - {} due to node addrs {}".format(self.lower, self.upper, local_addrs))
                self.split()
                return self.insert(entry, local_addrs)

            if not quiet:
                RoutingTable.log.debug("Routing insert failed for {entry}", entry=entry)
            return False

        def split(self):
            bisector = (self.lower + self.upper) // 2
            RoutingTable.log.debug("Splitting bucket 0x{low}~0x{high} into 0x{low}~0x{mid} and 0x{mid}~0x{high}", low=hex(self.lower), mid=hex(bisector), high=hex(self.upper))
            contents = self.contents
            self.contents = None
            self.left_child = RoutingTable.Bucket(self.lower, bisector, self.k)
            self.right_child = RoutingTable.Bucket(bisector + 1, self.upper, self.k)
            for entry in contents:
                self.insert(entry, quiet=True)

        def covers(self, addr: bytes):
            return self.lower <= RoutingTable.bytes_to_int(addr) <= self.upper

        def query(self, addr):
            addr_int = RoutingTable.bytes_to_int(addr)

            if self.contents is not None:
                yield from sorted(self.contents,
                        key=lambda entry: addr_int ^ RoutingTable.bytes_to_int(entry.node_addr.addr))
            else:
                if addr_int & (self.left_child.lower ^ self.right_child.lower):
                    closer, further = self.right_child, self.left_child
                else:
                    closer, further = self.left_child, self.right_child
                yield from closer.query(addr)
                yield from further.query(addr)

        def get_contents(self):
            if self.contents is not None:
                return sorted(self.contents, key=lambda entry: entry.node_addr.addr)
            return self.left_child.get_contents() + self.right_child.get_contents()

#        def show(self, indent=0):
#            # convenience function for troubleshooting
#            spacing = ' '*4*indent
#            lower = '0x'+hex(self.lower)[2:].rjust(RoutingTable.L//4, '0')
#            upper = '0x'+hex(self.upper)[2:].rjust(RoutingTable.L//4, '0')
#            print(spacing, end='')
#            print('\n' + spacing + lower + ' - ' + upper)
#            if self.contents is None:
#                self.left_child.show(indent+1)
#                self.right_child.show(indent+1)
#            else:
#                if len(self.contents) == 0:
#                    print(spacing, end='')
#                    print("Empty")
#                else:
#                    for entry in self.get_contents():
#                        print(spacing, end='')
#                        print(entry)
#                    print(spacing + "({} entries)".format(len(self.contents)))

    def __init__(self, local_addrs=None):
        self.local_addrs = local_addrs or []
        self.root = self.Bucket(0, 2**self.L - 1, self.k)

    def query(self, addr, lookup_size=None):
        lookup_size = lookup_size or self.k
        peers = set()
        results = []

        for entry in self.root.query(addr):
            if entry.contact_info not in peers:
                peers.add(entry.contact_info)
                results.append(entry)
            if len(results) == lookup_size:
                break
        return results

    def insert(self, contact_info, node_addr):
        entry = RoutingEntry(contact_info, node_addr)
        return self.root.insert(entry, self.local_addrs)

    def reload(self, new_addrs=None, new_peers=None):
        # to be called after a local addr is replaced
        self.log.debug("Reloading routing table.")
        self.log.debug("New addrs: {new}", new=new_addrs)
        self.local_addrs = new_addrs or []

        contents = self.root.get_contents()
        self._rng.shuffle(contents)
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
