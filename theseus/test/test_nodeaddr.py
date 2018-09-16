from twisted.trial import unittest

import theseus.nodeaddr


class NodeAddressTests(unittest.TestCase):
    def setUp(self):
        self.backup_urandom = theseus.nodeaddr.urandom
        self.backup_time = theseus.nodeaddr.time

    def tearDown(self):
        theseus.nodeaddr.urandom = self.backup_urandom
        theseus.nodeaddr.time = self.backup_time

    def test_vector(self):
        def fake_urandom(n):
            return bytes(n)
        def fake_time():
            return 0x69696969  # = 1768515945 = Jan 15 2026

        # >>> argon2id.kdf(20, b'\x69\x69\x69\x69\x7f\x00\x00\x01', bytes(16), argon2id.OPSLIMIT_INTERACTIVE, argon2id.MEMLIMIT_INTERACTIVE)
        # b'\xcdK\x1f,\x9f\x94\xfa\x0fB\xd5\x99\x1b\xbc\x9e\x92\xc1\xc3X\x0cs'
        expected = b'\xcdK\x1f,\x9f\x94\xfa\x0fB\xd5\x99\x1b\xbc\x9e\x92\xc1\xc3X\x0cs'

        theseus.nodeaddr.urandom = fake_urandom
        theseus.nodeaddr.time = fake_time

        d = theseus.nodeaddr.NodeAddress.new("127.0.0.1")
        d.addCallback(lambda result: self.assertEqual(expected, result.addr))
        return d
