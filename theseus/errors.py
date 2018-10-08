errcodes = {}


def errcode(cls):
    errcodes[cls.errcode] = cls
    return cls


######## 1xx errors

class KRPCError(Exception):
    """
    Generic error superclass for protocol errors.
    Defaults to error 100.
    """
    errcode = 100
    errtext = "Generic KRPC error"


@errcode
class Error100(KRPCError):
    pass


@errcode
class Error101(KRPCError):
    errcode = 101
    errtext = "Invalid KRPC message"


@errcode
class Error102(KRPCError):
    errcode = 102
    errtext = "Internal error (KRPC)"


@errcode
class Error103(KRPCError):
    errcode = 103
    errtext = "Method not recognized"


######## 2xx errors

class TheseusProtocolError(KRPCError):
    """
    For protocol errors on Theseus DHT RPCs specifically.
    Defaults to error 200.
    """
    errcode = 200
    errtext = "Generic DHT error"


@errcode
class Error200(TheseusProtocolError):
    pass


@errcode
class Error201(TheseusProtocolError):
    errcode = 201
    errtext = "Invalid DHT protocol message"


@errcode
class Error202(TheseusProtocolError):
    errcode = 202
    errtext = "Internal error (DHT)"


######## 3xx errors

@errcode
class Error300(TheseusProtocolError):
    pass


@errcode
class Error301(TheseusProtocolError):
    errcode = 301
    errtext = "Rate-limiting active"


######## Internal errors


class BencodeError(Exception):
    pass


class TheseusConnectionError(Exception):
    pass


class RetriesExceededError(Exception):
    pass


class DuplicateContactError(Exception):
    pass


class PluginError(Exception):
    pass


class ValidationError(Exception):
    pass


class AddrLookupConfigError(Exception):
    pass
