from twisted.protocols.policies import ProtocolWrapper, WrappingFactory
from twisted.internet.protocol import Protocol

from noise.connection import NoiseConnection

from .enums import INITIATOR


class NoiseProtocol(ProtocolWrapper):
    def __init__(self, factory, wrappedProtocol, noise_name=b'Noise_NN_25519_ChaChaPoly_BLAKE2b'):
        super().__init__(factory, wrappedProtocol)

        self._noise = None
        self._pending_writes = []
        self._recv_buf = b''
        self._recv_bytes_left = None  # populated after handshake
        self._pending_len_msg = None  # populated after handshake
        self.noise_name = noise_name

    def makeConnection(self, transport):
        Protocol.makeConnection(self, transport)  # don't call ProtocolWrapper.makeConnection until the channel is ready to write() to
        self.startHandshake()

    def startHandshake(self):
        if self._noise is not None:
            return

        # initialize Noise state
        self._noise = NoiseConnection.from_name(self.noise_name)

        if self.factory.role is INITIATOR:
            self._noise.set_as_initiator()
            self._noise.start_handshake()
            self.transport.write(self._noise.write_message())
        else:
            self._noise.set_as_responder()
            self._noise.start_handshake()

    def dataReceived(self, data):
        # is this handshake data?
        if self._noise.handshake_finished:
            self._handleCiphertext(data)
        else:
            self._handleHandshake(data)

    def _handleHandshake(self, data):
        self._noise.read_message(data)  # discard any payload

        if not self._noise.handshake_finished:
            self.transport.write(self._noise.write_message())

        if self._noise.handshake_finished:
            # we're in business!
            self._recv_bytes_left = 20
            self._expecting_len_msg = True

            while self._pending_writes:
                self.write(self._pending_writes.pop(0))

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
            # we got a full message & then some
            data = self._recv_buf[:self._recv_bytes_left]
            self._recv_buf = self._recv_buf[self._recv_bytes_left:]

        msg = self._noise.decrypt(data)

        if self._pending_len_msg:
            self._recv_bytes_left = (msg[0] << 24) + (msg[1] << 16) + (msg[2] << 8) + msg[3]
        else:
            super().dataReceived(data)
            self._recv_bytes_left = 20

        self._pending_len_msg = not self._pending_len_msg

        if len(self._recv_buf) > self._recv_bytes_left:
            self._handleCiphertext(b'')

    def write(self, data):
        if self._noise is not None and self._noise.handshake_finished:
            data = self._noise.encrypt(data)
            super().write(data)
        else:
            self._pending_writes.append(data)


class NoiseFactory(WrappingFactory):
    protocol = NoiseProtocol

    def __init__(self, wrapped_factory, role):
        super().__init__(wrapped_factory)

        self.role = role


class NoiseSettings:
    def __init__(self, local_key=None, remote_key=None, chunk_strategy=None):
        self.local_key = local_key
        self.remote_key = remote_key
        self.chunk_strategy = chunk_strategy

    def chunker(self):
        if self.chunk_strategy is None:
