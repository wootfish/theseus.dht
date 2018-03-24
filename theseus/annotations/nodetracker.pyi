from twisted.internet.defer import Deferred
from twisted.internet.protocol import Factory

from .bencode import BdecodeOutput
from .contactinfo import ContactInfo
from ..enums import NodeCnxnStates, NodeInfoKeys
from .noisewrapper import NoiseWrapper
from .peer import PeerService
from .protocol import DHTProtocol
from .protocols import IReactorTCPProtocol

from typing import Type, Optional, Union, AnyStr, Any, Dict, overload


# NOTE: should wrapping protocols have generics for what they wrap? can they, optionally, WLOG?
# (also can/should we do the same for Deferreds, w/ optional generics for expected callback/errback types?)


class NodeState(Factory):
    cnxn: Optional[DHTProtocol]
    host: Optional[str]
    state: Optional[NodeCnxnStates]

    @classmethod
    def fromContact(cls, contact_info: ContactInfo) -> "NodeState": ...
    @classmethod
    def fromProto(cls, protocol: NoiseWrapper) -> "NodeState": ...
    def connect(self, reactor: IReactorTCPProtocol) -> Deferred: ...
    def disconnect(self) -> None: ...
    def query(self, query_name: AnyStr, args: Dict[AnyStr, Any]) -> Deferred: ...
    def getContactInfo(self) -> ContactInfo: ...
    @overload
    def getInfo(self, info_key: NodeInfoKeys) -> BdecodeOutput: ...
    @overload
    def getInfo(self, info_key: NodeInfoKeys, defer: bool) -> Union[BdecodeOutput, Deferred]: ...  # TODO check whether this return type is ok


class NodeTracker(Factory):
    def __init__(self, parent: PeerService) -> None: ...
    def registerContact(self, contact_info: ContactInfo) -> NodeState: ...
    def getByContact(self, contact_info: ContactInfo) -> NodeState: ...
    def getByProto(self, protocol: DHTProtocol) -> NodeState: ...
