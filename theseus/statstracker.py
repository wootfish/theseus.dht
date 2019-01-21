from random import SystemRandom
from collections import deque
from time import clock

from twisted.logger import Logger

from .errors import NotEnoughLookupsError
from .constants import k, L


class StatsTracker:
    log = Logger()
    _rand = SystemRandom
    _clock = clock
    time_window = 3600
    min_sample_size = 3

    def __init__(self, local_peer):
        self.measurements = deque(maxlen=1024)
        self.local_peer = local_peer

    @staticmethod
    def _xor(addr1, addr2):
        n = 0
        for i, byte in enumerate(addr1):
            n <<= 8
            n += byte ^ addr2[i]
        return n

    def start(self):
        ...  # TODO recurring lookups for addrs from self._rand

    def stop(self):
        ...  # TODO stop recurring lookups

    def trim_old_measurements(self):
        while self._clock() - self.measurements[0][0] > self.time_window:
            self.measurements.popleft()

    def get_size(self):
        self.log.debug("Attempting network size estimation.")
        self.trim_old_measurements()
        sample_size = len(self.measurements)
        if sample_size < self.min_sample_size:
            self.log.debug("Not enough samples for size estimate ({s}/{m})", s=sample_size, m=self.min_sample_size)
            raise NotEnoughLookupsError

        self.log.debug("Sample size: {s}", s=sample_size)
        d_i = [0]*k
        for ts, distances in self.measurements:
            for i, d in enumerate(distances):
                d_i[i] += d / sample_size
        estimate = k*(k+1)*(2*k+1) / (6*sum(i*d/2**L for i, d in enumerate(d_i, 1)))
        self.log.debug("Current network size estimate: {n}", n=estimate)
        return estimate

    def register_lookup(self, d, addr):
        def cb(nodes):
            self.log.debug("Callback on lookup for {addr} starting.", addr=addr.hex())
            distances = sorted(
                self._xor(addr, routing_entry.node_addr.addr)
                for routing_entry in nodes
            )
            self.measurements.append((self._clock(), distances))
            self.trim_old_measurements()
            try:
                n = self.get_size()
                self.log.debug("Lookup callback hit. Current size estimate: {n}", n=n)
            except NotEnoughLookupsError:
                self.log.debug("Not enough lookups to make a size estimate...")
            return nodes

        self.log.debug("Registering lookup for {addr}", addr=addr.hex())
        d.addCallback(cb)
