from twisted.trial import unittest
from twisted.test.proto_helpers import AccumulatingProtocol, StringTransportWithDisconnection
from twisted.internet.protocol import Factory
from twisted.internet.address import IPv4Address

from theseus.noisewrapper import NoiseFactory
from theseus.enums import INITIATOR, RESPONDER

from noise.connection import Keypair, NoiseConnection

import warnings


class NoiseVectors(unittest.TestCase):
    def setUp(self):
        # these values should be populated within each test
        self.messages = None
        self.noise_1 = None
        self.noise_2 = None
        self.handshake_hash = None

        # these ones are constant across all test vectors
        self.prologue = bytes.fromhex("50726f6c6f677565313233")
        self.init_ephemeral = bytes.fromhex("893e28b9dc6ca8d611ab664754b8ceb7bac5117349a4439a6b0569da977c464a")
        self.resp_ephemeral = bytes.fromhex("bbdb4cdbd309f1a1f2e1456967fe288cadd6f712d65dc7b7793d5e63da6b375b")

    def _run_test(self):
        with warnings.catch_warnings(record=True) as w:
            self.noise_1.set_as_initiator()
            self.noise_1.set_prologue(self.prologue)
            self.noise_1.set_keypair_from_private_bytes(Keypair.EPHEMERAL, self.init_ephemeral)
            self.noise_1.start_handshake()

            self.noise_2.set_as_responder()
            self.noise_2.set_prologue(self.prologue)
            self.noise_2.set_keypair_from_private_bytes(Keypair.EPHEMERAL, self.resp_ephemeral)
            self.noise_2.start_handshake()

            self.assertEqual(len(w), 2)

            expected_warning = "One of ephemeral keypairs is already set. This is OK for testing, but should NEVER happen in production!"
            for warning in w:
                self.assertTrue(issubclass(warning.category, UserWarning))
                self.assertEqual(''.join(warning.message.args), expected_warning)

        for i, message in enumerate(self.messages):
            payload, ciphertext = message
            sender, receiver = (self.noise_1, self.noise_2)[::1 if i % 2 == 0 else -1]

            if sender.handshake_finished:
                c = sender.encrypt(payload)
                self.assertEqual(c, ciphertext)
                self.assertEqual(receiver.decrypt(c), payload)
            else:
                c = sender.write_message(payload)
                self.assertEqual(c, ciphertext)
                self.assertEqual(receiver.read_message(c), payload)

        for noise_cnxn in (self.noise_1, self.noise_2):
            self.assertTrue(noise_cnxn.handshake_finished)
            self.assertEqual(noise_cnxn.noise_protocol.handshake_hash, self.handshake_hash)

    def test_NN_25519_ChaChaPoly_BLAKE2b(self):
        self.noise_1 = NoiseConnection.from_name(b'Noise_NN_25519_ChaChaPoly_BLAKE2b')
        self.noise_2 = NoiseConnection.from_name(b'Noise_NN_25519_ChaChaPoly_BLAKE2b')

        self.handshake_hash = bytes.fromhex("d726c33acef40f118b1dfad1898936b432f07576ad892dd40cf206bd8157366962082641f6519a49f415a3b32713e6e596f3629e5572170cd1c08e92bc08f7a9")
        self.messages = (
                (bytes.fromhex("4c756477696720766f6e204d69736573"), bytes.fromhex("ca35def5ae56cec33dc2036731ab14896bc4c75dbb07a61f879f8e3afa4c79444c756477696720766f6e204d69736573")),
                (bytes.fromhex("4d757272617920526f746862617264"), bytes.fromhex("95ebc60d2b1fa672c1f46a8aa265ef51bfe38e7ccb39ec5be34069f144808843d10cf8ef4ab895bed3e4673211f0c93ba112a1eb52acf3a3f459cdd5715955")),
                (bytes.fromhex("462e20412e20486179656b"), bytes.fromhex("e50ec882703a1f34bf4957d8cafd036d34e02930f672f424c676e1")),
                (bytes.fromhex("4361726c204d656e676572"), bytes.fromhex("35bb2a728d3e8e5f47781d486089e4a37c5c2e4261256f44569a9f")),
                (bytes.fromhex("4a65616e2d426170746973746520536179"), bytes.fromhex("69ee82006e16b79438a34ad9de37ee44d83c267e355750ecf49f194b5c50403030")),
                (bytes.fromhex("457567656e2042f6686d20766f6e2042617765726b"), bytes.fromhex("c568b641b01d2f644f2a890538c359915ca50552e55129c029d3721866c2646a7af3fd1eff")),
                )

        self._run_test()

    def test_NK_25519_ChaChaPoly_BLAKE2b(self):
        init_remote_static = bytes.fromhex("31e0303fd6418d2f8c0e78b91f22e8caed0fbe48656dcf4767e4834f701b8f62")
        self.noise_1 = NoiseConnection.from_name(b'Noise_NK_25519_ChaChaPoly_BLAKE2b')
        self.noise_1.set_keypair_from_public_bytes(Keypair.REMOTE_STATIC, init_remote_static)

        resp_static = bytes.fromhex("4a3acbfdb163dec651dfa3194dece676d437029c62a408b4c5ea9114246e4893")
        self.noise_2 = NoiseConnection.from_name(b'Noise_NK_25519_ChaChaPoly_BLAKE2b')
        self.noise_2.set_keypair_from_private_bytes(Keypair.STATIC, resp_static)

        self.handshake_hash = bytes.fromhex("ae43dd84698159fea33f3638733584bedb74378bd418576f6cbfbb6702c483f7e6ef17408a2aa6a991bd6758dff089253c571816b0340145ed34f6e1844ed03a")
        self.messages = (
                (bytes.fromhex('4c756477696720766f6e204d69736573'), bytes.fromhex('ca35def5ae56cec33dc2036731ab14896bc4c75dbb07a61f879f8e3afa4c7944f3041e39b0c8ba56008f2d1183fea6acc9a221fce2945fd4e40396e046e0246b')),
                (bytes.fromhex('4d757272617920526f746862617264'), bytes.fromhex('95ebc60d2b1fa672c1f46a8aa265ef51bfe38e7ccb39ec5be34069f1448088432281dcc1835131f305dca14525e15e95bbefa674d47a13fdf88fe9c79dfca5')),
                (bytes.fromhex('462e20412e20486179656b'), bytes.fromhex('357e24e9f28ba22080666f7efacc01b2a0a4e358e742aeeff2aaf5')),
                (bytes.fromhex('4361726c204d656e676572'), bytes.fromhex('8b23b34ff3169de06a39551e969ca7876cc5122a4acff74bf2ec29')),
                (bytes.fromhex('4a65616e2d426170746973746520536179'), bytes.fromhex('5c104779b6f36e59fca73ed94b0ae092eae1d76dd109caf5060aaaedba385d7076')),
                (bytes.fromhex('457567656e2042f6686d20766f6e2042617765726b'), bytes.fromhex('34ae0518d0cd3aa641ed372ea94935ceecd87f8c4b422ce21a33d3f6f5493891e3e915d83f')),
                )

        self._run_test()

    def test_KN_25519_ChaChaPoly_BLAKE2b(self):
        init_static = bytes.fromhex("e61ef9919cde45dd5f82166404bd08e38bceb5dfdfded0a34c8df7ed542214d1")
        self.noise_1 = NoiseConnection.from_name(b'Noise_KN_25519_ChaChaPoly_BLAKE2b')
        self.noise_1.set_keypair_from_private_bytes(Keypair.STATIC, init_static)

        resp_remote_static = bytes.fromhex("6bc3822a2aa7f4e6981d6538692b3cdf3e6df9eea6ed269eb41d93c22757b75a")
        self.noise_2 = NoiseConnection.from_name(b'Noise_KN_25519_ChaChaPoly_BLAKE2b')
        self.noise_2.set_keypair_from_public_bytes(Keypair.REMOTE_STATIC, resp_remote_static)

        self.handshake_hash = bytes.fromhex("92cc6f032fcb8a139b6a3181e8f4741313da195bfe01404f0664ded4b89ca7a6504c09869d916f321af8e1e1d85d965faa92af9cc6db1cdf641466969055eebb")
        self.messages = (
                (bytes.fromhex('4c756477696720766f6e204d69736573'), bytes.fromhex('ca35def5ae56cec33dc2036731ab14896bc4c75dbb07a61f879f8e3afa4c79444c756477696720766f6e204d69736573')),
                (bytes.fromhex('4d757272617920526f746862617264'), bytes.fromhex('95ebc60d2b1fa672c1f46a8aa265ef51bfe38e7ccb39ec5be34069f144808843d7179edeba31152b3bf6a6c287040181777b61538630f4ff72695e3a1c9fa8')),
                (bytes.fromhex('462e20412e20486179656b'), bytes.fromhex('4f4945412bb3480c283fded0104a71c248ad9a39963324e9fe5887')),
                (bytes.fromhex('4361726c204d656e676572'), bytes.fromhex('07ddf2cec5a015dcd50dbb9b5ee61febc436db6b0f4e6a6a7c88da')),
                (bytes.fromhex('4a65616e2d426170746973746520536179'), bytes.fromhex('c5df36d437206734b09b1a1a3d4e382283f3b45141d5db0485121fb8e652aeab37')),
                (bytes.fromhex('457567656e2042f6686d20766f6e2042617765726b'), bytes.fromhex('3a4b0ded5d48b644b40a2226ec009866b4470506319e66fe678c55d8ee66727368aa08924a')),
                )

        self._run_test()

    def test_KK_25519_ChaChaPoly_BLAKE2b(self):
        init_static = bytes.fromhex("e61ef9919cde45dd5f82166404bd08e38bceb5dfdfded0a34c8df7ed542214d1")
        init_remote_static = bytes.fromhex("31e0303fd6418d2f8c0e78b91f22e8caed0fbe48656dcf4767e4834f701b8f62")
        self.noise_1 = NoiseConnection.from_name(b'Noise_KK_25519_ChaChaPoly_BLAKE2b')
        self.noise_1.set_keypair_from_private_bytes(Keypair.STATIC, init_static)
        self.noise_1.set_keypair_from_public_bytes(Keypair.REMOTE_STATIC, init_remote_static)

        resp_static = bytes.fromhex("4a3acbfdb163dec651dfa3194dece676d437029c62a408b4c5ea9114246e4893")
        resp_remote_static = bytes.fromhex("6bc3822a2aa7f4e6981d6538692b3cdf3e6df9eea6ed269eb41d93c22757b75a")
        self.noise_2 = NoiseConnection.from_name(b'Noise_KK_25519_ChaChaPoly_BLAKE2b')
        self.noise_2.set_keypair_from_private_bytes(Keypair.STATIC, resp_static)
        self.noise_2.set_keypair_from_public_bytes(Keypair.REMOTE_STATIC, resp_remote_static)

        self.handshake_hash = bytes.fromhex("449b8bddaf3d2f8999318d213d1db80a90d373bac67ce7aafcc444fc895414a97e82fb7797b2ae85f29199856789e9b8aef2a58faa828267ba4f2b09d89692d3")
        self.messages = (
                (bytes.fromhex('4c756477696720766f6e204d69736573'), bytes.fromhex('ca35def5ae56cec33dc2036731ab14896bc4c75dbb07a61f879f8e3afa4c7944f79a1d4b21fc3ea4a0c87213b8b4f05921228879fb74ea0d39ffc64619dc9658')),
                (bytes.fromhex('4d757272617920526f746862617264'), bytes.fromhex('95ebc60d2b1fa672c1f46a8aa265ef51bfe38e7ccb39ec5be34069f144808843e20b1bf85731f75d7e21b5d54baaa6a1dd8690bb26b34c92c02b152d726c01')),
                (bytes.fromhex('462e20412e20486179656b'), bytes.fromhex('25bfaa58833b07cdd6af7c07f2c51daac681a8ac0a02dd373259bd')),
                (bytes.fromhex('4361726c204d656e676572'), bytes.fromhex('ef586cff556dec8ef0053871ff0d4bf3f2c72e842487ec6d1da69f')),
                (bytes.fromhex('4a65616e2d426170746973746520536179'), bytes.fromhex('3265d50513550a354425d0218ba1e5f25d4994ce8990e6964398dba5982dbcbd85')),
                (bytes.fromhex('457567656e2042f6686d20766f6e2042617765726b'), bytes.fromhex('f11c02d5c3223d7b9281b52e1b134962b91bc3bfbd1646354dab9fc19b66bf6c1e0a6f431e')),
                )

        self._run_test()



class NoiseWrapper(unittest.TestCase):
    def setUp(self):
        silly_factory = Factory.forProtocol(AccumulatingProtocol)
        silly_factory.protocolConnectionMade = None  # for some reason AccumulatingProtocol expects this property to exist??

        addr_1 = IPv4Address("TCP", "127.0.0.1", 1337)
        addr_2 = IPv4Address("TCP", "127.0.0.1", 4200)

        self.noise_factory_1 = NoiseFactory(silly_factory, INITIATOR)
        self.noise_factory_2 = NoiseFactory(silly_factory, RESPONDER)

        self.noise_1 = self.noise_factory_1.buildProtocol(addr_2)
        self.noise_2 = self.noise_factory_2.buildProtocol(addr_1)

    def test_initial_handshake(self):
        self.transport_1 = StringTransportWithDisconnection()
        self.transport_2 = StringTransportWithDisconnection()

        self.noise_1.makeConnection(self.transport_1)
        self.noise_2.makeConnection(self.transport_2)

        self.assertFalse(self.noise_1.wrappedProtocol.made)
        self.assertFalse(self.noise_2.wrappedProtocol.made)

        msg_1 = self.transport_1.value()
        self.transport_1.clear()

        self.assertEqual(len(msg_1), 32)  # 32-byte key
        self.assertEqual(len(self.transport_2.value()), 0)

        self.noise_2.dataReceived(msg_1)
        msg_2 = self.transport_2.value()
        self.transport_2.clear()

        self.assertEqual(len(self.transport_1.value()), 0)
        self.assertEqual(len(msg_2), 48)  # 32-byte block (& same-sized key) + 16-byte AE block
        self.assertTrue(self.noise_2.wrappedProtocol.made)
        self.assertFalse(self.noise_1.wrappedProtocol.made)

        self.noise_1.dataReceived(msg_2)
        self.assertTrue(self.noise_1.wrappedProtocol.made)
