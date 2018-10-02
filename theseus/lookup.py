from twisted.internet.defer import Deferred, DeferredList, inlineCallbacks, fail
from twisted.internet.task import deferLater
from twisted.internet import reactor
from twisted.logger import Logger

from .errors import AddrLookupConfigError, TheseusConnectionError
from .routing import RoutingEntry
from .constants import k


class AddrLookup:
    log = Logger()
    clock = reactor

    target = None
    num_paths = k // 2
    path_width = 2
    query_timeout = 5
    num_peers = k

    _start_retry = 0.1

    running = False

    def __init__(self, local_peer=None):
        self.local_peer = local_peer
        self.callbacks = []
        self.seen_set = set()

    def configure(self, **kwargs):
        # self, target=None, num_paths=None, path_width=None, query_timeout=None, num_peers=None
        # target: bytes
        # TODO: add paranoia
        self.target = kwargs.get('target', self.target)
        self.num_paths = kwargs.get('num_paths', self.num_paths)
        self.path_width = kwargs.get('path_width', self.path_width)
        self.query_timeout = kwargs.get('query_timeout', self.query_timeout)
        self.num_peers = kwargs.get('num_peers', self.num_peers)

    def start(self):
        # returns a Deferred that will fire on completion
        if None in (self.target, self.num_paths, self.path_width):
            raise AddrLookupConfigError("missing required parameter")

        if self.running:
            self.callbacks.append(Deferred())
            return self.callbacks[-1]

        starting_set = set(self.local_peer.routing_table.query(self.target))

        if len(starting_set) == 0:
            # might happen at startup after local ID generation
            if self._start_retry < 1:
                self._start_retry += 0.1
                self.log.debug("Not enough peers to look up {target}. Retrying in {t} seconds.", target=self.target, t=self._start_retry)
                return deferLater(self.clock, self._start_retry, self.start)
            else:
                return fail(Exception("Retries exceeded"))

        self.log.info("Starting lookup for {target}", target=self.target)

        self.running = True
        d = Deferred()
        self.callbacks.append(d)

        self.log.debug("Starting set of peers for {target} lookup: {starting_set}", target=self.target, starting_set=starting_set)
        paths = [self.lookup_path(starting_set) for _ in range(self.num_paths)]
        DeferredList(paths).addCallback(self.on_completion)

        return d

    @inlineCallbacks
    def on_completion(self, dl_result):
        self.log.info("Routing queries for {target} complete.", target=self.target)

        paranoia_added = yield False # TODO paranoia here
        peer_set = set()

        for success, result in dl_result:
            if not success:
                continue
            peer_set.update(result)

        result = sorted(self.trim_entries(peer_set), key=self.get_distance)[:self.num_peers]
        self.log.debug("Results in lookup for {target}: {result}", target=self.target, result=result)
        while self.callbacks:
            self.callbacks.pop().callback(result)

        self.running = False
        self.seen_set = set()
        self._start_retry = AddrLookup._start_retry

    def get_distance(self, routing_entry):
        n = 0
        for i, byte in enumerate(routing_entry.node_addr.addr):
            n <<= 8
            n += byte ^ self.target[i]
        return n

    @inlineCallbacks
    def lookup_path(self, lookup_set):
        self.log.debug("Starting lookup step with set {lookup_set}, seen set {seen_set}", lookup_set=lookup_set, seen_set=self.seen_set)
        try:
            candidates = lookup_set.difference(self.seen_set)
            if len(candidates) == 0:  # TODO or if the closest candidate is super far
                return lookup_set

            targets = sorted(candidates, key=self.get_distance)[:self.path_width]
            self.seen_set.update(targets)

            if len(self.seen_set) > 10000:
                self.log.warn("Something is very fucky")
                raise Exception("something's fucky")

            queries = []
            for entry in lookup_set:
                try:
                    peer = self.local_peer.get_peer(entry.contact_info)
                except TheseusConnectionError:
                    continue
                queries.append(peer.query('find', {'addr': self.target}, timeout=self.query_timeout))

            self.log.debug("Querying {n} of {m} peers.", n=len(queries), m=len(lookup_set))

            responses = yield DeferredList(queries)
            new_peers = set(entry
                    for success, peers in responses if success
                    for entry in peers.get(b'nodes', []))

            self.log.debug("Queries for lookup step complete. Number of peers returned: {n}", n=len(new_peers))

            # this naively trusts addrs by default, which may or may not change
            entries = yield DeferredList([RoutingEntry.from_bytes(peer, trusted=True) for peer in new_peers])
            new_set = set(entry for success, entry in entries if success)
            new_set = self.trim_entries(new_set)
            self.log.debug("Size of trimmed peer set: {n}", n=len(new_set))
            return (yield self.lookup_path(new_set))

        except Exception as e:
            self.log.failure("Error in addr lookup")
            return lookup_set

    def trim_entries(self, entries):
        # utility method: given a set of routing entries, returns a trimmed set
        # with one entry per contact using the closest of that contact's addrs.
        d = {}
        for entry in entries:
            if entry.contact_info in d:
                if self.get_distance(d[entry.contact_info]) > self.get_distance(entry):
                    d[entry.contact_info] = entry
            else:
                d[entry.contact_info] = entry
        return set(entry for contact, entry in d.items())
