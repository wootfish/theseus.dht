from twisted.internet.defer import Deferred, fail
from twisted.internet.threads import deferToThread
from twisted.logger import Logger

from nacl import pwhash

from .enums import UNSET

from functools import lru_cache, total_ordering
from heapq import heappush, heappop
from time import time


@total_ordering
class HashJob:
    log = Logger()
    active = True

    def __init__(self, priority, preimage, d=None):
        self.priority = priority
        self.preimage = preimage
        self.d = d or Deferred()

    def deactivate(self):
        self.active = False

    def __lt__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return self.priority < other.priority or (self.priority == other.priority and self.active and not other.active)

    def __repr__(self):
        if self.active:
            return "HashJob({pre}, {pri})".format(pre=self.preimage, pri=self.priority.name)
        else:
            return "HashJob({pre}, {pri}, False)".format(pre=self.preimage, pri=self.priority.name)


class Hasher:
    log = Logger()

    OPSLIMIT = pwhash.argon2id.OPSLIMIT_MODERATE
    MEMLIMIT = pwhash.argon2id.MEMLIMIT_MODERATE
    #OPSLIMIT = pwhash.argon2id.OPSLIMIT_INTERACTIVE
    #MEMLIMIT = pwhash.argon2id.MEMLIMIT_INTERACTIVE
    MAX_THREADS = 3
    LRU_CACHE_SIZE = 500

    def __init__(self):
        self.priority_queue = []
        self.curr_jobs = []

    def checkNodeID(self, node_id, preimage, priority, check_timestamp=True):
        self.log.debug("Checking node ID {node_id} ({priority})", node_id=node_id, priority=priority)

        if check_timestamp and time() - self.timestampBytesToInt(preimage[:4]) > 2**16:
            self.log.debug("ID check for {node_id} failed: timestamp expired", node_id=node_id)
            return fail(Exception("timestamp expired"))

        d = self.getNodeID(preimage, priority)
        d.addCallback(lambda result: result == node_id)
        return d

    def getNodeID(self, preimage, priority=UNSET):
        # if there's already a pending job with this preimage w/ a lower
        # priority, deactivate it & steal the associated Deferred
        for job in self.priority_queue:
            if job.preimage == preimage and job.active and job.priority < priority:
                self.log.debug("Upgrading hash job for {preimage} from priority {old} to {new}", preimage=preimage, old=job.priority, new=priority)
                job.deactivate()
                new_job = HashJob(priority, preimage, job.d)
                break
        else:
            new_job = HashJob(priority, preimage)
            self.log.debug("Adding {job}", job=new_job)

        heappush(self.priority_queue, new_job)
        self._maybeAddJobs()
        return new_job.d

    def _callback(self, result, preimage):
        self.log.debug("Hash job for {preimage} complete. Result: {result}", preimage=preimage, result=result)

        # swap out the completed job
        self.curr_jobs = [job for job in self.curr_jobs if job.preimage != preimage]
        self._maybeAddJobs()

        # pass the result on to other callbacks
        return result

    def _maybeAddJobs(self):
        job = None

        # loop for as long as we have both unclaimed jobs and free threads
        while (len(self.curr_jobs) < self.MAX_THREADS) and self.priority_queue:
            job = heappop(self.priority_queue)
            if not job.active:
                continue

            self.log.info("Starting {job}", job=job)
            d_thread = deferToThread(Hasher._kdf, job.preimage, bytes(16))
            d_thread.addCallback(self._callback, job.preimage)
            d_thread.chainDeferred(job.d)
            self.curr_jobs.append(job)

        self.log.info("Active hash jobs: {n} ({m} in queue)", n=len(self.curr_jobs), m=len(self.priority_queue))

    @staticmethod
    @lru_cache(maxsize=LRU_CACHE_SIZE)
    def _kdf(input_data, salt):
        return pwhash.argon2id.kdf(20, input_data, salt, opslimit=Hasher.OPSLIMIT, memlimit=Hasher.MEMLIMIT)

    @staticmethod
    def timestampBytesToInt(timestamp):
        n = 0
        for byte in timestamp:
            n <<= 8
            n += byte
        return n


hasher = Hasher()
