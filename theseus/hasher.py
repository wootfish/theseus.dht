from twisted.internet.defer import Deferred, inlineCallbacks, succeed, DeferredList
from twisted.internet.threads import deferToThread
from twisted.logger import Logger

from nacl.pwhash import argon2id

from functools import lru_cache
from queue import PriorityQueue
import itertools

from .enums import UNSET


class Hasher:
    log = Logger()

    # TODO: can we get away with pushing these higher? (particularly memlimit)
    # NOTE: OPSLIMIT and MEMLIMIT must be left constant once hashing has begun,
    # to maintain accuracy of LRU cache contents
    OPSLIMIT = argon2id.OPSLIMIT_INTERACTIVE
    MEMLIMIT = argon2id.MEMLIMIT_INTERACTIVE

    MAX_THREADS = 3  # TODO should these be worker processes instead? does the GIL keep these threads from actually being useful?
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
        try:
            if self.queue.empty() or self.active_jobs == self.MAX_THREADS:
                return

            job = self.queue.get()
            while job[1] not in self.callbacks:
                job = self.queue.get()
            self.active_jobs += 1
            image = yield deferToThread(self._kdf, *job[1])
            self.log.debug("Priority {priority} hash job complete. {inputs} -> {output}", priority=job[0].name, inputs=job[1], output=image)
            for d in self.callbacks.pop(job[1], []):
                try:
                    d.callback(image)
                except Exception:
                    self.log.failure("Error in hash job callback")
            self.active_jobs -= 1
            self._update_jobs()

        except Exception as e:
            self.log.failure("Unexpected error in hasher")
            raise e

    @staticmethod
    @lru_cache(maxsize=LRU_CACHE_SIZE)
    def _kdf(message, salt):
        return argon2id.kdf(20, message, salt, Hasher.OPSLIMIT, Hasher.MEMLIMIT)

    def exhaust(self):
        if len(self.callbacks) == 0:
            return succeed(None)

        # wait for current jobs to complete, then wait for new jobs too (if any)
        d = DeferredList(list(itertools.chain(*self.callbacks.values())))
        d.addCallback(lambda _: self.exhaust())
        return d


hasher = Hasher()
