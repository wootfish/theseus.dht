from nacl import pwhash

from twisted.logger import Logger
from twisted.internet.defer import Deferred, fail
from twisted.internet.threads import deferToThread

from time import time
from heapq import heappush, heappop
from functools import lru_cache

from .enums import UNSET, IDCheckPriorities


class Hasher:
    log = Logger()

    OPSLIMIT = pwhash.argon2id.OPSLIMIT_MODERATE
    MEMLIMIT = pwhash.argon2id.MEMLIMIT_MODERATE
    MAX_THREADS = 3
    LRU_CACHE_SIZE = 500

    def __init__(self):
        self.priority_queue = []
        self.curr_jobs = []

    def checkNodeID(self, node_id, preimage, priority, check_timestamp = True):
        self.log.debug("Checking node ID {node_id} ({priority})", node_id=node_id, priority=priority)

        if check_timestamp and time() - self.timestampBytesToInt(preimage[:4]) > 2**16:
            self.log.debug("ID check for {node_id} failed: timestamp expired", node_id=node_id)
            return fail(Exception("timestamp expired"))

        d = self.getNodeID(preimage, priority)
        d.addCallback(lambda result: result == node_id)
        return d

    def getNodeID(self, preimage, priority = UNSET):
        # job[0]: priority
        # job[1]: Boolean flag which, if set to False, says to skip this job
        #         (used when upgrading job priority -- it's cheaper than
        #         popping the old job, which would break the heap invariant)
        # job[2]: KDF input (node_id)
        # job[3]: Deferred that'll callback when job is done

        d = Deferred()

        # if there's already a job for this preimage + a lower priority,
        # deactivate it & steal the associated Deferred
        for job in self.priority_queue:
            _priority, _flag, _preimage, _d = job

            if not _flag or _preimage != preimage:
                continue

            if priority > _priority:
                self.log.debug("Upgrading hash job for {preimage} from priority {old} to {new}", preimage=preimage, old=_priority, new=priority)
                job[1] = False
                d = _d
                break
        else:
            self.log.debug("Adding hash job for {preimage}, priority {priority}.", preimage=preimage, priority=priority)

        # push our new job onto the heap
        new_job = [priority, True, preimage, d]
        heappush(self.priority_queue, new_job)
        self._maybeAddJobs()

        return d

    def _callback(self, result):
        self.log.debug("Hash job completed, result: {result}", result=result)

        # filter out the completed job
        self.curr_jobs = [job for job in self.curr_jobs if not job[3].called]

        # if we have room for more jobs, add 'em
        self._maybeAddJobs()

        # pass the result on to other callbacks
        return result

    def _maybeAddJobs(self):
        while (len(self.curr_jobs) < self.MAX_THREADS) and self.priority_queue:
            job = heappop(self.priority_queue)
            _, flag, preimage, d_job = job

            if not flag:
                continue

            self.log.info("Starting ID check job for {preimage}", preimage=preimage)
            d_thread = deferToThread(Hasher._kdf, preimage, bytes(16))
            d_thread.addCallback(self._callback)
            d_thread.chainDeferred(d_job)
            self.curr_jobs.append(job)

        self.log.info("Job(s) added.")

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
