from twisted.trial import unittest
from twisted.internet.defer import Deferred, DeferredList

from theseus.hasher import Hasher


class HasherTests(unittest.TestCase):
    def setUp(self):
        self.hasher = Hasher()

    def tearDown(self):
        pending = []
        for job in self.hasher.callbacks.values():
            pending += job
        return DeferredList(pending)

    def test_vector(self):
        message = b'secret'
        salt = b'saltsaltsaltsalt'
        expected = b'e\x90^]\x1b\\\xcb\xc5\xb1+wD\x9e.\x06Rz\xb6\x05u'

        d = self.hasher.do_hash(message, salt)
        self.assertIsInstance(d, Deferred)
        #self.assertEqual(expected, self.successResultOf(d))
        d.addCallback(lambda result: self.assertEqual(result, expected))
