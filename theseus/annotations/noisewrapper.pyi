from twisted.protocols.policies import ProtocolWrapper

from noise.connection import NoiseConnection
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

from typing import Optional

from .enum import NoiseProtoRoles


class NoiseWrapper(ProtocolWrapper):
    settings: Optional['NoiseSettings']
    _noise: Optional[NoiseConnection]

    def startHandshake(self) -> None: ...
    def dataReceived(self, data: bytes) -> None: ...
    def _handleHandshake(self, data: bytes) -> None: ...
    def _handleCiphertext(self, data: bytes) -> None: ...
    def write(self, data: bytes) -> None: ...
    @staticmethod
    def _len_int_to_bytes(i: int) -> bytes: ...
    @staticmethod
    def _len_bytes_to_int(i: bytes) -> int: ...
    @staticmethod
    def getDefaultConfig() -> 'NoiseSettings': ...


class NoiseSettings:
    role: NoiseProtoRoles
    noise_name: bytes
    local_static: Optional[X25519PrivateKey]
    remote_static: Optional[X25519PublicKey]

    def __init__(self, role: NoiseProtoRoles, noise_name: bytes, local_static=Optional[X25519PrivateKey], remote_static=Optional[X25519PublicKey]) -> None: ...
    def __repr__(self) -> str: ...
