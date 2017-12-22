"""
Provides functionality for encoding Python3 data types to Bencode format and
vice versa.
"""

from twisted.logger import Logger

from .errors import BencodeError


log = Logger()


def bencode(data):
    if type(data) in (bytes, bytearray):
        return _bencode_bytes(data)
    elif type(data) is str:
        return _bencode_bytes(data.encode("utf-8"))
    elif type(data) is int:
        return _bencode_int(data)
    elif type(data) in (list, tuple):
        return _bencode_list(data)
    elif type(data) is dict:
        return _bencode_dict(data)
    else:
        log.debug("Error trying to bencode {data}", data=data)
        raise BencodeError("Tried to bencode data with unsupported type {}".format(type(data)))


def bdecode(data):
    if type(data) is str:
        data = data.encode("utf-8")  # for more convenient interactive use

    if len(data) == 0:
        raise BencodeError("Tried to bdecode an empty string")

    result, stop_ind = _bdecode(data)
    if stop_ind != len(data):
        raise BencodeError("bdecoding finished before end of input data")

    return result


def _bdecode(data):
    byte_digits = [ord(str(i)) for i in range(10)]

    if data[0] == ord('i'):
        return _bdecode_int(data)
    elif data[0] == ord('l'):
        return _bdecode_list(data)
    elif data[0] == ord('d'):
        return _bdecode_dict(data)
    elif data[0] in byte_digits:
        return _bdecode_bytes(data)
    else:
        log.debug("Error trying to bdecode {data}", data=data)
        raise BencodeError("Data to decode not in proper bencode format")


def _bencode_bytes(data):
    return str(len(data)).encode("ascii") + b':' + data


def _bencode_int(data):
    return b'i' + str(data).encode("ascii") + b'e'


def _bencode_list(data):
    return b'l' + b''.join(bencode(elem) for elem in data) + b'e'


def _bencode_dict(data):
    result = b'd'

    for key in data:
        if type(key) not in (str, bytes):
            log.debug("Error bencoding data {data}", data=data)
            raise BencodeError("keys of dictionary to bencode must be bytestrings")

    for key in sorted(data, key=lambda s: s if type(s) is bytes else s.encode("UTF-8")):
        result += bencode(key)
        result += bencode(data[key])
    result += b'e'
    return result


# These _bdecode methods accept a bencoded value followed by arbitrary data.
# They return 2-tuples containing first the decoded data in its native Python
# representation, and second the index at which the decoded value terminates.
# This second value is important for recursive decoding and for making sure
# we've consumed all available data


def _bdecode_int(data):
    try:
        endpoint = data.index(b'e')
        result = int(data[1:endpoint])
    except (ValueError, IndexError):
        log.debug("Error bdecoding data {data}", data=data)
        raise BencodeError("Improperly formatted bencoded int field")

    return (result, endpoint+1)


def _bdecode_list(data):
    l = []
    ind = 1
    try:
        while data[ind] != ord('e'):
            datum, offset = _bdecode(data[ind:])
            ind += offset
            l.append(datum)
    except IndexError:
        log.debug("Error bdecoding data {data}", data=data)
        raise BencodeError("Improperly formatted bencoded list field")
    return (l, ind+1)


def _bdecode_dict(data):
    d = {}
    ind = 1
    try:
        while data[ind] != ord('e'):
            key, offset = _bdecode(data[ind:])
            if key in d:
                raise BencodeError("Keys in bencoded dictionary must be unique")
            if type(key) is not bytes:
                raise BencodeError("Keys in bencoded dictionary must be bytestrings")
            ind += offset
            val, offset = _bdecode(data[ind:])
            ind += offset
            d[key] = val

    except IndexError:
        log.debug("Error bdecoding data {data}", data=data)
        raise BencodeError("Improperly formatted bencoded dict field")
    return (d, ind+1)


def _bdecode_bytes(data):
    try:
        sep_ind = data.index(b':')
        bytes_len = int(data[:sep_ind])
        assert bytes_len >= 0
        assert len(data[sep_ind+1:]) >= bytes_len
        result = data[sep_ind+1:sep_ind+1+bytes_len]
    except (ValueError, IndexError, AssertionError):
        log.debug("Error bdecoding data {data}", data=data)
        raise BencodeError("Improperly formatted bencoded bytes field")
    return (result, sep_ind+bytes_len+1)
