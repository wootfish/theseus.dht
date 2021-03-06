from twisted.internet.task import LoopingCall
from twisted.logger import Logger

from sys import getsizeof

from heapq import heappush, heappop
from time import time

from .constants import L


class DataStore:
    log = Logger()

    interval = 1

    memlimit = 2**20  # 2**20 bytes = roughly one megabyte (and change)
    default_duration = 60*60  # 1 hour, in seconds
    looper = None

    def __init__(self, local_addr=None, memlimit=None, default_duration=None):
        # local_addr: bytes
        self.log.info("Initializing data store for {a}", a=None if local_addr is None else local_addr.hex())

        self.local_addr = local_addr
        self.memlimit = memlimit or self.memlimit
        self.default_duration = default_duration or self.default_duration

        self.looper = LoopingCall(self.check_timeouts)
        self.data = {}
        self.running_total = 0

    def _get_distance(self, addr):
        if self.local_addr is None:
            return 0

        n = 0
        for i, byte in enumerate(self.local_addr):
            n <<= 8
            n += byte ^ self.local_addr[i]
        return n

    def _choose_duration(self, addr, sizeof):
        if self.running_total + sizeof >= self.memlimit:
            self.log.debug("Memlimit reached, declining to store new data")
            return 0

        # TODO analyze and maybe adjust these two eqns once the dust settles
        memfactor = 1 - (self.running_total / self.memlimit)
        addrfactor = 1 - (self._get_distance(addr) / 2**(L-4))  # this may be negative for large distances
        duration = int(self.default_duration * memfactor * addrfactor)
        self.log.debug("Setting storage duration for {n}-byte datum (current storage: {s}/{l}): memfactor={m}, addrfactor={a}, duration={d}", s=self.running_total, l=self.memlimit, n=sizeof, m=memfactor, a=addrfactor, d=duration)
        return max(duration, 0)

    def put(self, addr, datum, tags=None, suggested_duration=None):
        # tags: Dict[bytes, bytes]
        self.log.debug("Received put query for {hexaddr}: {datum}", hexaddr=addr.hex(), datum=datum)
        tags = tags or {}
        suggested_duration = suggested_duration or float('inf')

        if len(tags) > 0:
            tag_names = tuple(sorted(tags.keys()))
            tag_values = [tags[name] for name in tag_names]
            datum = [datum, *tag_values]
            datum_size = getsizeof(datum) + sum(getsizeof(bs) for bs in datum)
        else:
            tag_names = tuple()
            datum_size = getsizeof(datum)

        duration = min(suggested_duration, self._choose_duration(addr, datum_size))

        if duration > 0:
            if not self.looper.running:
                self.looper.start(self.interval)

            timeout = int(time()) + duration
            heappush(self.data.setdefault(tag_names, []), (timeout, addr, datum))

        return duration

    def get(self, address=None, tag_names=tuple()):
        # tag_names: Iterable
        tag_names = tuple(sorted(tag_names))

        if address is None:
            data = {}
            for ts, addr, datum in self.data.get(tag_names, []):
                data.setdefault(addr, []).append(datum)
            return data
        else:
            return [datum for ts, addr, datum in self.data.get(tag_names, []) if addr == address]

    def check_timeouts(self):
        to_trim = []

        for tags in self.data:
            data = self.data[tags]
            while len(data) > 0 and data[0][0] < time():
                self.running_total -= getsizeof(heappop(data))
            if len(data) == 0:
                to_trim.append(tags)

        for tags in to_trim:
            self.data.pop(tags)

        if len(self.data) == 0:
            self.looper.stop()
