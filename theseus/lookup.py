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
    prefix = ""
    num_paths = k // 2
    path_width = 2
    query_timeout = 5
    num_peers = k

    _start_retry = 0.5

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
        self.prefix = self.target.hex() + ' '

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
            if self._start_retry < 5:
                self._start_retry += 0.5
                self.log.debug(self.prefix + "Not enough peers. Retrying in {t} seconds.", target=self.target, t=self._start_retry)
                return deferLater(self.clock, self._start_retry, self.start)
            else:
                return fail(Exception("Retries exceeded"))


        self.running = True
        d = Deferred()
        self.callbacks.append(d)
        self.log.info(self.prefix + "Starting lookup for {target}", target=self.target)
        self.log.debug(self.prefix + "Starting peers: {starting_set}", target=self.target, starting_set=starting_set)
        num_paths = min(self.num_paths, (len(starting_set) + (self.path_width - 1)) // self.path_width)
        paths = [self.lookup_path(starting_set, i) for i in range(num_paths)]
        DeferredList(paths).addCallback(self.on_completion)

        return d

    def on_completion(self, dl_result):
        self.log.info(self.prefix + "Routing queries complete. {n} routing entries found before trimming.", n=len(dl_result))

        trimmed_results = {}
        for success, result in dl_result:
            if not success:
                continue
            for entry in result:
                if entry.contact_info in self.local_peer.blacklist \
                        or entry.contact_info.key.public_bytes == self.local_peer.peer_key.public_bytes:
                    continue
                addr = trimmed_results.setdefault(entry.contact_info, entry).node_addr
                if self.get_distance(addr) > self.get_distance(entry.node_addr):
                    trimmed_results[entry.contact_info] = entry

        result = sorted(trimmed_results,
                key=lambda c: self.get_distance(trimmed_results[c].node_addr)
                )[:self.num_peers]

        self.log.debug(self.prefix + "{n} Lookup results: {result}", n=len(result), result=result)
        while self.callbacks:
            self.callbacks.pop().callback(result)

        self.running = False
        self.seen_set = set()
        self._start_retry = AddrLookup._start_retry

    def get_distance(self, node_addr):
        n = 0
        for i, byte in enumerate(node_addr.addr):
            n <<= 8
            n += byte ^ self.target[i]
        return n

    @inlineCallbacks
    def lookup_path(self, lookup_set, path_num):
        try:
            # trim the lookup set to get a list of peers to iterate on
            self.log.debug(self.prefix + "(path {n}) Starting lookup step. Lookup set = {lookup_set}, seen set = {seen_set}", n=path_num, lookup_set=lookup_set, seen_set=self.seen_set)
            candidates = {}
            for entry in lookup_set:
                if entry.contact_info in self.seen_set \
                        or entry.contact_info in self.local_peer.blacklist \
                        or entry.contact_info.key.public_bytes == self.local_peer.peer_key.public_bytes:
                    continue
                addr = candidates.setdefault(entry.contact_info, entry.node_addr)
                if self.get_distance(addr) > self.get_distance(entry.node_addr):
                    candidates[entry.contact_info] = entry.node_addr

            # if we don't have any new peers to talk to, call it a day
            if len(candidates) == 0:
                self.log.debug(self.prefix + "(path {n}) End of lookup path reached. {m} results.", n=path_num, m=len(lookup_set))
                return lookup_set

            # otherwise, find the closest candidates and call dibs on them
            targets = sorted(candidates, key=lambda c: self.get_distance(candidates[c]))[:self.path_width]
            self.seen_set.update(targets)

            if len(self.seen_set) > 10000:  # you may laugh, but it's been known to happen
                self.log.warn(self.prefix + "(path {n}) Lookup is off the rails", n=path_num)
                raise Exception("something's fucky")

            self.log.debug(self.prefix + "(path {n}) Querying {m} peer(s): {targets}", n=path_num, m=len(targets), targets=targets)
            queries = []
            for contact in targets:
                try:
                    peer = self.local_peer.get_peer(contact)
                except TheseusConnectionError:
                    continue
                queries.append(peer.query('find', {'addr': self.target}, timeout=self.query_timeout))

            # wait on those query deferreds to fire, then combine the results
            responses = yield DeferredList(queries)
            new_peers = set(entry
                    for success, peers in responses if success
                    for entry in peers.get(b'nodes', []))

            self.log.debug(self.prefix + "(path {n}) Lookup step's 'find' queries complete. Number of routing entries returned: {m}", n=path_num, m=len(new_peers))

            # get routing entries for the returned results (TODO currently this will blindly trust addrs by default, which is very naive)
            entries = yield DeferredList([RoutingEntry.from_bytes(peer, trusted=True) for peer in new_peers])
            new_set = set(entry for success, entry in entries if success)

            # iterate on this new set of routing entries, and augment the results if necessary
            # (TODO since addr distance is not necessarily monotonically
            # decreasing across iterated lookup steps, this might not end up
            # adding the ideal peers -- is it worth trying to address this?)

            results = (yield self.lookup_path(new_set, path_num))
            if len(results) < self.num_peers:
                self.log.debug(self.prefix + "(path {n}) Collecting results. Augmenting {x} returned entries with {y} local ones.", n=path_num, x=len(results), y=len(lookup_set))
                results.update(lookup_set)
            return results

        except Exception as e:
            self.log.failure(self.prefix + "Internal error in lookup")
            return lookup_set
