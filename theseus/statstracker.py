from random import SystemRandom
from collections import deque
from time import clock


class StatsTracker:
    _rand = SystemRandom
    time_window = 3600

    def __init__(self, local_peer):
        self.estimates = deque(maxlen=1024)
        self.local_peer = local_peer

    def start(self):
        ...  # TODO recurring lookups

    def stop(self):
        ...  # TODO stop recurring lookups

    def trim_old_estimates(self):
        while time.clock() - self.estimates[0][0] > self.time_window:
            self.estimates.popleft()

    def get_size_estimate(self):
        self.trim_old_estimates()
        return 17  # TODO do beta fit on self.estimates

    def register_lookup(self, d, addr):
        def cb(value):
            self.trim_old_estimates()
            self.estimates.append(17)  # TODO calculate size estimate from results
            return value

        d.addCallback(cb)  # TODO maybe only add callback if addr is not close to an addr we already have an estimate for?
