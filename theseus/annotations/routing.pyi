from twisted.logger import Logger
from typing import Union, Tuple, Set, Any

from .peer import PeerService
from .contactinfo import ContactInfo


_BUCKET_TYPE = Tuple[int, int]


class RoutingTable:
    log: Logger
    k: int

    def __init__(self, parent: PeerService) -> None: ...
    def __contains__(self, contact: ContactInfo) -> bool: ...
    def _bucketLookup(self, node_address: bytes) -> _BUCKET_TYPE: ...
    def _bucketIsSplitCandidate(self, bucket: _BUCKET_TYPE) -> bool: ...
    def _bucketSplit(self, bucket: _BUCKET_TYPE) -> bool: ...
    def insert(self, contact_info: ContactInfo) -> None: ...
    def _insert(self, contact_info: ContactInfo, node_id: bytes) -> None: ...
    def discard(self, contact_info: ContactInfo) -> None: ...
    def query(self, target_addr: bytes) -> Set[ContactInfo]: ...
    def pretty(self) -> None: ...
    @staticmethod
    def getNodeIDs(contact_info: ContactInfo) -> Any: ...  # return type TODO (list of bytes?)
    @staticmethod
    def bytesToInt(node_id: bytes) -> int: ...
