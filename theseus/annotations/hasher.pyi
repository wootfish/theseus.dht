from twisted.internet.defer import Deferred

from ..enums import UNSET, IDCheckPriorities


class Hasher:
    OPSLIMIT: int
    MEMLIMIT: int
    MAX_THREADS: int
    LRU_CACHE_SIZE: int

    def __init__(self) -> None: ...
    def checkNodeID(self, node_id: bytes, preimage: bytes, priority: IDCheckPriorities, check_timestamp: bool) -> Deferred: ...
    def getNodeID(self, preimage: bytes, priority: IDCheckPriorities) -> Deferred: ...
    def _callback(self, result: bytes) -> bytes: ...
    def _maybeAddJobs(self) -> None: ...
    @staticmethod
    def _kdf(input_data: bytes, salt: bytes) -> bytes: ...  # NOTE: in hasher.py, _kdf is decorated with @functools.lru_cache -- doesn't seem like we should need that here, but... we might?
    @staticmethod
    def timestampBytesToInt(timestamp: bytes) -> int: ...


hasher: Hasher
