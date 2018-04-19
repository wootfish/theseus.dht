def netstringify(bytestring):
    return str(len(bytestring)).encode("ascii") + b":" + bytestring + b","


def unnetstringify(netstring, asserter):
    asserter.assertIn(b":", netstring)
    i, string = netstring.split(b":", 1)
    asserter.assertEqual(string[-1], b','[0])
    string = string[:-1]
    asserter.assertEqual(int(i), len(string))
    return string
