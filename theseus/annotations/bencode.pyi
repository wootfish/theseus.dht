from typing import Union, Any, Tuple, List, Dict


BencodeInput = Union[bytes, bytearray, str, int, list, tuple, dict]
BdecodeOutput = Union[int, list, dict, bytes]


def bencode(data: BencodeInput) -> bytes: ...
def bdecode(data: bytes) -> BdecodeOutput: ...
def _bdecode(data: bytes) -> Tuple[BdecodeOutput, int]: ...
def _bencode_bytes(data: bytes) -> bytes: ...
def _bencode_int(data: int) -> bytes: ...
def _bencode_list(data: Union[list, tuple]) -> bytes: ...  # TODO determine, is data: Union[list, tuple] ok or should we annotate with something more generic like Iterable (and rename the function)?
def _bencode_dict(data: dict) -> bytes: ...
def _bdecode_int(data: bytes) -> Tuple[int, int]: ...
def _bdecode_list(data: bytes) -> Tuple[List[BdecodeOutput], int]: ...
def _bdecode_dict(data: bytes) -> Dict[BdecodeOutput, BdecodeOutput]: ...
def _bdecode_bytes(data: bytes) -> bytes: ...
