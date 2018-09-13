from twisted.internet.defer import Deferred, fail, inlineCallbacks
from twisted.internet.threads import deferToThread
from twisted.logger import Logger

from nacl.pwhash import argon2id

from functools import lru_cache, total_ordering
from heapq import heappush, heappop
from time import time

from queue import PriorityQueue

from .enums import UNSET


class Hasher:
    # TODO: can we get away with pushing these higher? (particularly memlimit)
    # NOTE: OPSLIMIT and MEMLIMIT must be left constant once hashing has begun,
    # to maintain accuracy of LRU cache contents
    OPSLIMIT = argon2id.OPSLIMIT_INTERACTIVE
    MEMLIMIT = argon2id.MEMLIMIT_INTERACTIVE

    MAX_THREADS = 3  # should these be worker processes instead? does the GIL mess us up here?
    LRU_CACHE_SIZE = 500

    def __init__(self):
        self.queue = PriorityQueue()
        self.callbacks = {}
        self.active_jobs = 0

    def do_hash(self, message, salt, priority):
        inputs = (message, salt)
        self.queue.put((priority, inputs))
        d = Deferred()
        self.callbacks.setdefault(inputs, []).append(d)
        self._update_jobs()
        return d

    @inlineCallbacks
    def _update_jobs(self):
        if self.queue.empty() or self.active_jobs == self.MAX_THREADS:
            return

        job = self.queue.get()
        while job[1] not in callbacks:
            job = self.queue.get()
        self.active_jobs += 1
        image = yield deferToThread(self._kdf, *job[1])
        for d in self.callbacks.pop(job[1], []):
            d.callback(image)
        self.active_jobs -= 1
        self._update_jobs()

    @lru_cache(maxsize=LRU_CACHE_SIZE)
    @staticmethod
    def _kdf(message, salt):
        return argon2id.kdf(20, input_data, salt, Hasher.OPSLIMIT, Hasher.MEMLIMIT)


hasher = Hasher()
