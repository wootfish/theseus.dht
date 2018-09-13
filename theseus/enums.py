from enum import Enum, IntEnum

# PeerStateKeys members are used as keys to the Dispatcher's internal 'states'
# dict.
PeerStateKeys = Enum("PeerStateKeys", "ROLE STATE LAST_ACTIVE INFO CNXN")
ROLE, STATE, LAST_ACTIVE, INFO, CNXN = (PeerStateKeys.ROLE,
        PeerStateKeys.STATE, PeerStateKeys.LAST_ACTIVE, PeerStateKeys.INFO,
        PeerStateKeys.CNXN)


# NoiseProtoRoles enumerate possible protocol roles in the Noise Framework. The
# Noise protocol initiator for a connection's initial handshake is always the
# same as the initiator for the TCP connection itself. In further handshakes,
# however, the initiator may be either party.
NoiseProtoRoles = Enum("NoiseProtoRoles", "INITIATOR RESPONDER")
INITIATOR, RESPONDER = NoiseProtoRoles.INITIATOR, NoiseProtoRoles.RESPONDER


# PeerCnxnStates are the possible values associated with PeerStateKeys.STATE
PeerCnxnStates = Enum("NodeCnxnStates", "DISCONNECTED CONNECTING CONNECTED")
DISCONNECTED, CONNECTING, CONNECTED = (PeerCnxnStates.DISCONNECTED,
        PeerCnxnStates.CONNECTING, PeerCnxnStates.CONNECTED)


# DHTInfoKeys enum members have their associated ASCII key bytes as values
class DHTInfoKeys(Enum):
    MAX_VERSION = b'max_version'
    LISTEN_PORT = b'listen_port'
    PEER_KEY = b'peer_key'
    IDS = b'ids'


MAX_VERSION, LISTEN_PORT, PEER_KEY, IDS = (DHTInfoKeys.MAX_VERSION,
        DHTInfoKeys.LISTEN_PORT, DHTInfoKeys.PEER_KEY, DHTInfoKeys.IDS)


# IDCheckPriorities are used in the hasher's internal priority queue. They are
# IntEnum so that direct comparisons can be made between enum elements (lower
# values are higher priority)
IDCheckPriorities = IntEnum("IDCheckPriorities", "CRITICAL HIGH MEDIUM LOW UNSET")
CRITICAL, HIGH, MEDIUM, LOW, UNSET = (IDCheckPriorities.CRITICAL,
        IDCheckPriorities.HIGH, IDCheckPriorities.MEDIUM,
        IDCheckPriorities.LOW, IDCheckPriorities.UNSET)
