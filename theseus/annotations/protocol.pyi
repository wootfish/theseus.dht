from twisted.logger import Logger
from twisted.protocols.policies import TimeoutMixin
from twisted.internet.defer import Deferred

from .krpc import KRPCProtocol

from typing import Any


# not to be confused with protocols.pyi  :)


class DHTProtocol(KRPCProtocol, TimeoutMixin):
    log: Logger
    idle_timeout: int

    def connectionMade(self) -> None: ...
    def find(self, args: Any) -> Deferred: ...  # TODO
    def get(self, args: Any) -> Deferred: ...  # TODO
    def info(self, args: Any) -> Deferred: ...  # TODO
    def put(self, args: Any) -> Deferred: ...  # TODO
    def onGet(self, args: Any) -> Deferred: ... # TODO
    def onInfo(self, args: Any) -> Deferred: ... # TODO
    def onPut(self, args: Any) -> Deferred: ... # TODO
