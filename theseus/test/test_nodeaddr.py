from twisted.trial import unittest

from unittest.mock import Mock, patch

from theseus.nodeaddr import NodeAddress, Preimage
from theseus.errors import ValidationError


@patch('theseus.nodeaddr.time', lambda: 0x69696969)
@patch('theseus.nodeaddr.urandom', lambda n: bytes(n))
class NodeAddressTests(unittest.TestCase):
    def test_vector(self):
        # >>> argon2id.kdf(20, b'\x69\x69\x69\x69\x7f\x00\x00\x01', bytes(16), argon2id.OPSLIMIT_INTERACTIVE, argon2id.MEMLIMIT_INTERACTIVE).hex()
        # 'cd4b1f2c9f94fa0f42d5991bbc9e92c1c3580c73'
        expected = bytes.fromhex('cd4b1f2c9f94fa0f42d5991bbc9e92c1c3580c73')

        d = NodeAddress.new("127.0.0.1")
        d.addCallback(lambda result: self.assertEqual(expected, result.addr))
        return d

    def test_from_trusted_preimage(self):
        pre = Preimage(bytes(4), bytes(4), bytes(6))
        d = NodeAddress.from_preimage(node_addr=bytes(20), preimage=pre, trusted=True)
        self.assertTrue(d.called)
        addr = d.result
        self.assertEqual(addr.addr, bytes(20))
        self.assertTrue(addr.preimage is pre)
        self.assertFalse(addr.verified)

    def test_rejecting_bad_timestamp(self):
        pre = Preimage(bytes(4), bytes(4), bytes(6))
        d = NodeAddress.from_preimage(node_addr=bytes(20), preimage=pre)
        fail = self.failureResultOf(d)
        self.assertEqual(fail.check(ValidationError), ValidationError)
        self.assertEqual(fail.getErrorMessage(), "Expired timestamp")

    def test_rejecting_missized_addr_bytes(self):
        self.assertRaises(Exception, NodeAddress.from_bytes, b'oops')  # TODO make the method raise a more specific exception, then update this
