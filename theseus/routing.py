from twisted.logger import Logger


class RoutingTable:
    log = Logger()
    k = 8

    def __init__(self, parent):
        self.parent = parent
        self.buckets = {(0, 2**160-1): set()}

    def __contains__(self, contact):
        for bucket in self.buckets.values():
            if contact in bucket:
                return True
            return False

    def _bucketLookup(self, addr):
        if type(addr) is bytes:
            addr = self.addrToInt(addr)

        for bucket in self.buckets:
            if bucket[0] <= addr <= bucket[1]:
                return bucket

    def _bucketSplit(self, bucket):
        # returns True if split was successful, False if it wasn't possible
        if bucket[0] == bucket[1]:
            self.log.warn("Weird edge case encountered: Failed to split bucket {bucket}", bucket=bucket)
            return False

        bisector = (bucket[0] + bucket[1]) // 2
        lower = bucket[0], bisector
        upper = bisector+1, bucket[1]
        self.buckets[lower] = {}
        self.buckets[upper] = {}

        for listen_addr, node_id in self.buckets.pop(bucket).items():
            self._insert(listen_addr, node_id)

        self.log.info("Routing table bucket {bucket} split. Current table state: {pretty}", bucket=(hex(bucket[0]), hex(bucket[1])), pretty=RoutingTable.pretty(self))
        return True

    def maybeInsert(self, contact_info):
        # returns True if the contact was inserted or is already in the table
        # returns False if the insert failed

        self.log.debug("Attempting to insert {contact} into routing table. (ID: {node_id})", contact=contact_info, node_id=contact_info.node_id)

        # currently in the process of moving this validation logic out of state objects & into peer.py
        #if listen_addr in self.buckets[bucket]:
        #    self.log.debug("Insert 'successful': {addr} already in routing table", addr=listen_addr)
        #    return True

        ## just for safety's sake, make sure this isn't a duplicate ID
        #for _listen_addr, _node_id in self.buckets[bucket].items():
        #    if node_id.address == _node_id.address:
        #        self.log.warn("Fail: Routing table collision for {addr} (other node: {other_addr})", addr=listen_addr, other_addr=_listen_addr)
        #        self.log.warn("This is VERY BAD and probably reflects a bug in the program -- the dispatcher should have prevented a duplicate ID from ever getting this far into program state!")
        #        return False

        bucket = self._bucketLookup(contact_info.address)

        # 1st: does the bucket have room?
        if len(self.buckets[bucket]) < self.k:
            self.buckets[bucket].add(contact_info)
            return True

        # 2nd: does the bucket qualify for a split?
        for node in self.node_manager:
            addr = node.node_id.address
            if addr is not None and bucket[0] <= self.addrToInt(addr) <= bucket[1]:
                break
        else:
            return False

        # split the bucket and retry the insert
        if self._bucketSplit(bucket):
            return self.maybeInsert(contact_info)
        else:
            return False

    def discard(self, contact_info):
        """
        Returns True if the address was found and removed.
        Returns False if the address was not found in the routing table.
        """
        for bucket in self.buckets.values():
            if contact_info in bucket:
                bucket.remove(contact_info)
                return True
        return False

    #def refresh(self):
    #    """
    #    Resets the routing table to a clean slate and re-inserts every node,
    #    one by one. Really only useful when a local node changes ID.
    #    """
    #    old_buckets = self.buckets
    #    self.buckets = {(0, 2**160-1): set()}

    #    for bucket in old_buckets.values():
    #        sorted_items = sorted(bucket.items(), key=lambda t: t[1])
    #        for listen_addr, node_id in sorted_items:
    #            self.insert(listen_addr, node_id)

    def query(self, target_addr, k=None):
        # if this turns out to be slow, it could probably be sped up by using
        # something like heapq instead of a full list comprehension+sort

        if k is None:
            k = self.k

        entries = [
                contact_info
                for bucket in self.buckets
                for contact_info in self.buckets[bucket]
                ]
        entries.sort(key=lambda contact_info: self.xor(contact_info.node_id, target_addr))
        return entries[:k]

    #def getCallbacks(self, addr):
    #    def on_find_query(args):
    #        target_addr = args.get(b"addr")
    #        assert type(target_addr) is bytes
    #        assert len(target_addr) == 20
    #        return {"nodes": self.query(target_addr)}

    #    def on_find_response(args):
    #        pass  # TODO what do we do here? surely the routing table wants this info

    #    return on_find_query, on_find_response

    @staticmethod
    def addrToInt(node_address):
        n = 0
        for byte in node_address:
            n <<= 8
            n += byte
        return n

    @staticmethod
    def xor(bytes_1, bytes_2):
        if bytes_1 is None or bytes_2 is None:
            return float('inf')
        return RoutingTable.addrToInt(bytes_1) ^ RoutingTable.addrToInt(bytes_2)

    @staticmethod
    def pretty(table):
        """
        Returns a prettyprintable representation of the given table's state.
        This mostly means converting things to hex where appropriate and
        boiling off some boilerplate.
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
