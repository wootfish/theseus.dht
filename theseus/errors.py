errcodes = {}


def errcode(cls):
    errcodes[cls.errcode] = cls
    return cls


class TheseusProtocolError(Exception):
    """
    Generic error superclass for protocol errors.
    Defaults to error 300.
    """
    errcode = 300
    error_name = "Generic error"


@errcode
class Error100(TheseusProtocolError):
    errcode = 100
    error_name = "Invalid KRPC message"


@errcode
class Error101(TheseusProtocolError):
    errcode = 101
    error_name = "Internal error (KRPC)"


@errcode
class Error200(TheseusProtocolError):
    errcode = 200
    error_name = "Invalid DHT protocol message"


@errcode
class Error201(TheseusProtocolError):
    errcode = 201
    error_name = "Internal error (DHT)"


@errcode
class Error202(TheseusProtocolError):
    errcode = 202
    error_name = "Method not recognized"


@errcode
class Error203(TheseusProtocolError):
    errcode = 203
    error_name = "Tag not recognized"


@errcode
class Error300(TheseusProtocolError):
    pass


@errcode
class Error301(TheseusProtocolError):
    errcode = 301
    error_name = "Rate-limiting active"


class KRPCError(Exception):
    pass


class BencodeError(Exception):
    pass


class TheseusConnectionError(Exception):
    pass
