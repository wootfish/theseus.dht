from twisted.logger import Logger


class RoutingTable:
    log = Logger()
    k = 8

    def __init__(self, node_manager):
        self.node_manager = node_manager
        self.buckets = {(0, 2**160-1): {}}

    def __contains__(self, addr):
        for bucket in self.buckets.values():
            if addr in bucket:
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
        self.buckets[bucket[0], bisector] = set()
        self.buckets[bisector+1, bucket[1]] = set()

        for node in self.buckets.pop(bucket):
            self.insert(node, take_logs=False)

        self.log.info("Routing table bucket {bucket} split.", bucket=self._getPrintableBucket(bucket))
        return True

    def insert(self, listen_addr, node_id):
        # returns True if the addr was inserted or is already in the table,
        # False if the insert failed (e.g. bcause there wasn't room, or because
        # of an ID collision)

        self.log.debug("Attempting to insert {addr} into routing table. (ID: {node_id})", node=listen_addr, node_id=node_id)

        if node_id is None:
            self.log.warn("Fail: Tried to insert node with node_id=None (addr: {addr})", addr=listen_addr)
            return False

        if node_id.addr_check_retval is not True:
            self.log.debug("Fail: Tried to insert node into routing table without successful ID check. (addr: {addr}, ID: {node_id})", addr=listen_addr, node_id=node_id)
            return False

        bucket = self._bucketLookup(self, node_id.address)

        if listen_addr in self.buckets[bucket]:
            self.log.debug("Insert 'successful' ({addr} already in routing table)", addr=listen_addr)
            return True

        # just for safety's sake, make sure this isn't a duplicate ID
        for _listen_addr, _node_id in self.buckets[bucket].items():
            if node_id.address == _node_id.address:
                self.log.warn("Fail: Routing table collision for {addr} (other node: {other_addr})", addr=listen_addr, other_addr=_listen_addr)
                self.log.warn("This is VERY BAD and probably reflects a bug in the program -- the dispatcher should have prevented a duplicate ID from ever getting this far into program state!")
                return False

        # ok now it's off to the races
        result = self._insert(listen_addr, node_id)
        if result:
            self.log.debug("Insert for {addr} successful. Current routing table: {buckets}", addr=listen_addr, buckets=self.buckets)
        else:
            self.log.debug("Fail: Bucket for {addr} is full & can't be split.", addr=listen_addr)
        return result

    def _insert(self, listen_addr, node_id):
        bucket = self._bucketLookup(self, node_id.address)

        # is there room?
        if len(self.buckets[bucket]) < self.k:
            self.buckets[bucket][listen_addr] = node_id
            return True

        # does the bucket qualify for a split?
        for node in self.node_manager:
            addr = node.node_id.address
            if addr is not None and bucket[0] <= self.addrToInt(addr) <= bucket[1]:
                break
        else:
            return False

        # split the bucket and retry the insert
        if self._bucketSplit(bucket):
            return self._insert(listen_addr, node_id)
        else:
            return False

    def remove(self, addr):
        for bucket_dict in self.buckets.values():
            if addr in bucket_dict:
                del bucket_dict[addr]
                return

    def query(self, target_addr, k=None):
        # if this turns out to be slow it could probably be sped up by heapq
        # or by being lazy and just pulling contents of an addr's bucket (at cost of sometimes returning < k results)

        if k is None:
            k = self.k

        entries = [
                (self.xor(node_addr, target_addr), listen_addr)
                for bucket in self.buckets
                for listen_addr, node_addr in bucket.items()
                ]
        entries.sort()

        return [t[1] for t in entries[:k]]

    def getCallbacks(self, addr):
        def on_find_query(args):
            target_addr = args.get(b"addr")
            assert type(target_addr) is bytes
            assert len(target_addr) == 20
            return {"nodes": self.query(target_addr)}

        def on_find_response(args):
            pass  # TODO what do we do here? surely the routing table wants this info

        return on_find_query, on_find_response

    @staticmethod
    def addrToInt(node_address):
        n = 0
        for byte in node_address:
            n <<= 8
            n += byte
        return n

    @staticmethod
    def xor(bytes_1, bytes_2):
        return RoutingTable.addrToInt(bytes_1) ^ RoutingTable.addrToInt(bytes_2)
