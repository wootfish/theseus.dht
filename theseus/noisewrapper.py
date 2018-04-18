from twisted.protocols.policies import ProtocolWrapper
from twisted.logger import Logger

from noise.connection import NoiseConnection

from .enums import INITIATOR, RESPONDER, PEER_KEY

import struct


# NOTE: would it be possible to somehow integrate the default
# Int32StringReceiver in with NoiseWrapper? rather than re-implementing
# netstrings for the data the payloads of these encrypted messages? Probably
# not but food for thought.

# NOTE: open question for future pondering: which of the following seems like
# better style?
#       self.transport.write(bytes)
#       super().write(bytes)
# super().write runs self.transport.write so they're effectively the same
# currently the two are used interchangeably here. would be nice to normalize.

# NOTE: we need some way of extending the arbitrary-message-sizing property to
# handshake data as well as wrapped protocol message data. we can chunk
# arbitrarily but all handshake messages will still add up to 48 bytes. one
# idea: just allow random bytes to be appended to any non-terminal handshake
# messages (the terminal message handshake can just be followed by something
# like a no-op protocol message) are there any traffic patterns this scheme
# would not support?


class NoiseWrapper(ProtocolWrapper):
    log = Logger()
    settings = None
    MAX_LENGTH = 2**20

    _noise = None
    _buf = b''
    _bytes_needed = None  # populated after handshake
    _len_msg_pending = None  # populated after handshake
    _peer = None

    def __init__(self, factory, wrappedProtocol):
        super().__init__(factory, wrappedProtocol)

        self._pending_writes = []

    def makeConnection(self, transport):
        peer = transport.getPeer()
        self._peer = peer.host + ":" + str(peer.port)
        self.transport = transport
        if self.settings is None:
            self.settings = self.getDefaultConfig()
        self.factory.registerProtocol(self)
        self.startHandshake()

    def connectionLost(self, reason):
        self.log.info('{peer} - Connection lost. Details: "{reason}"', peer=self._peer, reason=reason.getErrorMessage())
        super().connectionLost(reason)

    def startHandshake(self):
        if self._noise is not None:
            self.log.warn("{peer} - startHandshake called with pre-existing Noise state", peer=self._peer)
            return

        if self.settings is None:
            self.log.warn("{peer} - Tried to startHandshake while self.settings is None!", peer=self._peer)
            raise Exception("Can't start handshake without parameters")

        self.log.info("{peer} - Noise handshake settings: {ctxt}", peer=self._peer, ctxt=self.settings)

        # initialize Noise state
        self._noise = NoiseConnection.from_name(self.settings.noise_name)
        self._bytes_needed = 48

        if self.settings.role is INITIATOR:
            if self.settings.remote_static is None:
                raise Exception("Missing required remote key data!")

            self._noise.noise_protocol.keypairs['rs'] = self.settings.remote_static
            self._noise.set_as_initiator()
            self._noise.start_handshake()
            message = self._noise.write_message()
            self.log.debug("{peer} - Sending {n} handshake bytes", peer=self._peer, n=len(message))
            self.transport.write(message)

        else:
            if self.settings.local_static is None:
                raise Exception("Missing required local key data!")

            self._noise.noise_protocol.keypairs['s'] = self.settings.local_static
            self._noise.set_as_responder()
            self._noise.start_handshake()

    def dataReceived(self, data):
        self.log.debug("{peer} - Received {n} bytes", peer=self._peer, n=len(data))
        if self._bytes_needed is None:
            raise Exception("data received before handshake started (self._bytes_needed is uninitialized)")

        # do we have a full message yet? if not, just return
        self._buf += data

        while len(self._buf) >= self._bytes_needed:
            data = self._buf[:self._bytes_needed]
            self._buf = self._buf[self._bytes_needed:]

            try:
                if self._len_msg_pending is None:
                    self.log.debug("{peer} - Consuming Noise handshake message", peer=self._peer)
                    self._processHandshake(data)
                elif self._len_msg_pending:
                    self.log.debug("{peer} - Consuming length announcement message", peer=self._peer)
                    self._processLength(data)
                else:
                    self.log.debug("{peer} - Consuming protocol message", peer=self._peer)
                    self._processMessage(data)

            except Exception:
                self.log.failure("Unexpected exception caused by received data {data}", data=data)
                self.log.info("{peer} - Terminating connection due to unexpected error.", peer=self._peer)
                self.transport.loseConnection()
                return

    def _processHandshake(self, data):
        self._noise.read_message(data)  # discard any payload

        if not self._noise.handshake_finished:
            msg = self._noise.write_message()
            self.log.debug("{peer} - Sending {n} handshake bytes", peer=self._peer, n=len(msg))
            self.transport.write(msg)

        if self._noise.handshake_finished:  # if read_message OR write_message completed the handshake
            # we're in business!
            self._bytes_needed = 20
            self._len_msg_pending = True

            while self._pending_writes:
                self.write(self._pending_writes.pop(0))

            self.log.info("{peer} - Noise handshake complete.", peer=self._peer)
            super().makeConnection(self.transport)

    def _processLength(self, data):
        msg = self._noise.decrypt(data)
        length = self._len_bytes_to_int(msg)
        self.log.debug("{peer} - Length announcement: {length}.", peer=self._peer, length=length)

        self._bytes_needed = length + 16
        self._len_msg_pending = not self._len_msg_pending

    def _processMessage(self, data):
        msg = self._noise.decrypt(data)
        super().dataReceived(msg)

        self._bytes_needed = 20
        self._len_msg_pending = not self._len_msg_pending

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

    @classmethod
    def forPeerState(cls, peer_state):
        return cls(peer_state.role, remote_static=peer_state.info[PEER_KEY])
