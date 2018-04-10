from twisted.protocols.policies import ProtocolWrapper
from twisted.logger import Logger

from noise.connection import NoiseConnection
from noise.exceptions import NoiseValueError

from .enums import INITIATOR, RESPONDER

import struct


# NOTE: would it be possible to somehow integrate the default NetstringReceiver
# in with NoiseWrapper? rather than re-implementing netstrings for the data the
# payloads of these encrypted messages?
# Or really we'd probably want to use Int32StringReceiver


class NoiseWrapper(ProtocolWrapper):
    log = Logger()
    settings = None
    _noise = None

    def __init__(self, factory, wrappedProtocol):
        super().__init__(factory, wrappedProtocol)

        self._pending_writes = []
        self._recv_buf = b''
        self._recv_bytes_left = None  # populated after handshake
        self._pending_len_msg = None  # populated after handshake

    def makeConnection(self, transport):
        self.transport = transport

        if self.settings is None:
            self.settings = self.getDefaultConfig()

        self.startHandshake()

    def connectionLost(self, reason):
        self.log.info("Connection lost with {addr}. {reason}", addr=self.getPeer(), reason=reason.getErrorMessage())
        super().connectionLost(reason)

    def startHandshake(self):
        if self._noise is not None:
            return

        if self.settings is None:
            self.log.warn("Tried to startHandshake with {addr} while self.settings is None!", addr=self.getPeer())
            raise Exception("Can't start handshake without parameters")

        self.log.info("Starting Noise handshake with {addr}, settings: {ctxt}", addr=self.getPeer(), ctxt=self.settings)

        # initialize Noise state
        self._noise = NoiseConnection.from_name(self.settings.noise_name)

        if self.settings.role is INITIATOR:
            if self.settings.remote_static is None:
                raise Exception("Missing required remote key data!")

            self._noise.noise_protocol.keypairs['rs'] = self.settings.remote_static
            self._noise.set_as_initiator()
            self._noise.start_handshake()
            self.transport.write(self._noise.write_message())
        else:
            if self.settings.local_static is None:
                raise Exception("Missing required local key data!")

            self._noise.noise_protocol.keypairs['s'] = self.settings.local_static
            self._noise.set_as_responder()
            self._noise.start_handshake()

    def dataReceived(self, data):
        self.log.info("Received {n} bytes from {addr}", n=len(data), addr=self.getPeer())
        try:
            if self._noise.handshake_finished:
                self._handleCiphertext(data)
            else:
                self._handleHandshake(data)
        except Exception as e:
            self.log.failure("Unexpected exception caused by received data {data}", data=data)
            self.log.info("Terminating connection to {peer} due to unexpected error.", peer=self.transport.getPeer())
            self.transport.loseConnection()

    def _handleHandshake(self, data):
        self._noise.read_message(data)  # discard any payload

        if not self._noise.handshake_finished:
            self.transport.write(self._noise.write_message())

        if self._noise.handshake_finished:
            # we're in business!
            self._recv_bytes_left = 20
            self._pending_len_msg = True

            while self._pending_writes:
                self.write(self._pending_writes.pop(0))

            self.log.info("Encrypted channel to {addr} established.", addr=self.getPeer())
            super().makeConnection(self.transport)

    def _handleCiphertext(self, data):
        # do we have a full message?
        self._recv_bytes_left -= len(data)
        self._recv_buf += data

        if self._recv_bytes_left > 0:
            return

        if self._recv_bytes_left == 0:
            data = self._recv_buf
            self._recv_buf = b''
        else:
            # self._recv_bytes_left < 0
            # meaning we got a full message & then some
            data = self._recv_buf[:self._recv_bytes_left]
            self._recv_buf = self._recv_buf[self._recv_bytes_left:]

        msg = self._noise.decrypt(data)

        if self._pending_len_msg:
            length = self._len_bytes_to_int(msg)
            self._recv_bytes_left = length + 16 - len(self._recv_buf)
            self.log.debug("Length announcement decrypted. Value: {length}. {m} bytes currently buffered, so waiting on {n} ciphertext bytes.", length=length, n=self._recv_bytes_left, m=len(self._recv_buf))
        else:
            self.log.debug("Protocol message decrypted. Message: {msg}", msg=msg)
            super().dataReceived(msg)
            self._recv_bytes_left = 20

        self._pending_len_msg = not self._pending_len_msg

        if len(self._recv_buf) >= self._recv_bytes_left:
            self._handleCiphertext(b'')

    def write(self, data):
        if self._noise is not None and self._noise.handshake_finished:
            # TODO once we're implementing message padding, add that here
            length_enc = self._noise.encrypt(self._len_int_to_bytes(len(data)))
            data_enc = self._noise.encrypt(data)

            super().write(length_enc)
            super().write(data_enc)
        else:
            self._pending_writes.append(data)

    @staticmethod
    def _len_int_to_bytes(i):
        return struct.pack(">L", i)

    @staticmethod
    def _len_bytes_to_int(b):
        return struct.unpack(">L", b)[0]

    @staticmethod
    def getDefaultConfig():
        from .app import peer
        return NoiseSettings(RESPONDER, local_static=peer.peer_key)


class NoiseSettings:
    def __init__(self, role, noise_name=b'Noise_NK_25519_ChaChaPoly_BLAKE2b', local_static=None, remote_static=None):
        self.role = role
        self.noise_name = noise_name
        self.local_static = local_static
        self.remote_static = remote_static

    def __repr__(self):
        return "NoiseSettings({}, {}, {}, {})".format(self.role, self.noise_name, self.local_static, self.remote_static)
