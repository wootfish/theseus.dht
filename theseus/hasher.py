from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.threads import deferToThread
from twisted.logger import Logger

from nacl.pwhash import argon2id

from functools import lru_cache
from queue import PriorityQueue

from .enums import UNSET


class Hasher:
    log = Logger()

    # TODO: can we get away with pushing these higher? (particularly memlimit)
    # NOTE: OPSLIMIT and MEMLIMIT must be left constant once hashing has begun,
    # to maintain accuracy of LRU cache contents
    OPSLIMIT = argon2id.OPSLIMIT_INTERACTIVE
    MEMLIMIT = argon2id.MEMLIMIT_INTERACTIVE

    MAX_THREADS = 3  # TODO should these be worker processes instead? does the GIL mess us up here?
    LRU_CACHE_SIZE = 500

    def __init__(self):
        self.queue = PriorityQueue()
        self.callbacks = {}
        self.active_jobs = 0

    def do_hash(self, message, salt, priority=UNSET):
        inputs = (message, salt)
        self.log.debug("Adding priority {priority} hash job for {inputs}", priority=priority.name, inputs=inputs)
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
        while job[1] not in self.callbacks:
            job = self.queue.get()
        self.active_jobs += 1
        image = yield deferToThread(self._kdf, *job[1])
        for d in self.callbacks.pop(job[1], []):
            d.callback(image)
        self.active_jobs -= 1
        self.log.debug("Priority {priority} hash job complete. {inputs} -> {output}", priority=job[0].name, inputs=job[1], output=image)
        self._update_jobs()

    @staticmethod
    @lru_cache(maxsize=LRU_CACHE_SIZE)
    def _kdf(message, salt):
        return argon2id.kdf(20, message, salt, Hasher.OPSLIMIT, Hasher.MEMLIMIT)


hasher = Hasher()
