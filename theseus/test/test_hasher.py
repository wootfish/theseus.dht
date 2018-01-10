from twisted.trial import unittest

from theseus.hasher import hasher


class HasherTests(unittest.TestCase):
    def test_vector(self):
        self.assertEqual(
                hasher._kdf(b'', bytes(16)),
                b'\xe5!\xad\xb2\xd4\xa0\x1eY\x9c\xe3d\xebL<Q\x91\xc9\x82QJ'
                )

    def test_id_get_and_check(self):
        d = hasher.getNodeID(b'')
        #d.addCallback(lambda node_id: self.assertTrue(self.successResultOf(hasher.checkNodeID(node_id, b''))))
        return d
