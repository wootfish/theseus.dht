def netstringify(bytestring):
    return str(len(bytestring)).encode("ascii") + b":" + bytestring + b","


def unnetstringify(netstring, asserter):
    assert b':' in netstring
    i, string = netstring.split(b":", 1)

    assert string[-1] == b','[0]
    string = string[:-1]

    assert int(i) == len(string)
    return string
