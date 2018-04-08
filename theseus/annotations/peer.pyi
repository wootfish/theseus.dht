from twisted.application.service import Service
from twisted.internet.defer import Deferred

from typing import AnyStr, Any, List

from .contactinfo import ContactInfo
from ..enums import NodeInfoKeys
from ..protocol import DHTProtocol


class PeerService(Service):
    def __init__(self, num_nodes: int) -> None: ...
    def startListening(self) -> int: ...
    def _listen(self, port: int) -> None: ...
    def addToBlacklist(self, host: AnyStr) -> None: ...
    def makeCnxn(self, contact_info: ContactInfo) -> Deferred: ...
    def maybeUpdateInfo(self, cnxn: DHTProtocol, info_key: NodeInfoKeys, new_value: Any) -> None: ...   # TODO should this return success/failure? or maybe raise an error on failure?
    def doLookup(self, addr: bytes, tags: List[AnyStr]): ...