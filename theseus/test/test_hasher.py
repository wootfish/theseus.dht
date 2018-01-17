from twisted.trial import unittest

from theseus.hasher import hasher


class HasherTests(unittest.TestCase):
    def test_vector(self):
        self.assertEqual(
                hasher._kdf(b'testvector', bytes(16)),
                b'`\r\xc5g\xf2\x11\xe40\xfa<i9\x9dG\xa2\x83\xd4uB<'
                )

    def test_id_get_and_check(self):
        def callback(node_id):
            d2 = hasher.checkNodeID(node_id, b'testvector', check_timestamp=False)
            d2.addCallback(self.assertTrue)
            return d2

        d = hasher.getNodeID(b'testvector')
        d.addCallback(callback)
        return d
