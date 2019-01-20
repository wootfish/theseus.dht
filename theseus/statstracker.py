from random import SystemRandom
from collections import deque
from time import clock

from .errors import NotEnoughLookupsError
from .constants import k, L


class StatsTracker:
    _rand = SystemRandom
    _clock = clock
    time_window = 3600

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
        self.trim_old_measurements()
        if len(self.measurements) < 10:
            raise NotEnoughLookupsError()

        sample_size = len(self.measurements)
        d_i = [0]*k
        for _, distances in self.measurements:
            for i, d in distances:
                d_i[i] += d / sample_size
        r_i = [dist / 2**L for dist in d_i]
        estimate = k*(k+1)*(2*k+1) / (6*sum(i*r for i, r in enumerate(r_i, 1)))
        return estimate

    def register_lookup(self, d, addr):
        def cb(self, nodes):
            distances = sorted(
                self._xor(addr, routing_entry.node_addr.addr)
                for routing_entry in nodes
            )
            self.measurements.append((self._clock(), distances))
            self.trim_old_measurements()
            return nodes

        d.addCallback(cb)

