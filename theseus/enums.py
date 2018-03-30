from enum import Enum, IntEnum

# NodeStateKeys members are used as keys to the Dispatcher's internal 'states'
# dict.
NodeStateKeys = Enum("NodeStateKeys", "ROLE STATE LAST_ACTIVE INFO CNXN")
ROLE, STATE, LAST_ACTIVE, INFO, CNXN = (NodeStateKeys.ROLE,
        NodeStateKeys.STATE, NodeStateKeys.LAST_ACTIVE, NodeStateKeys.INFO,
        NodeStateKeys.CNXN)


# NoiseProtoRoles enumerate possible protocol roles in the Noise Framework. The
# Noise protocol initiator for a connection's initial handshake is always the
# same as the initiator for the TCP connection itself. In further handshakes,
# however, the initiator may be either party.
NoiseProtoRoles = Enum("NoiseProtoRoles", "INITIATOR RESPONDER")
INITIATOR, RESPONDER = NoiseProtoRoles.INITIATOR, NoiseProtoRoles.RESPONDER


# NodeCnxnStates are the possible values associated with NodeStateKeys.STATE
NodeCnxnStates = Enum("NodeCnxnStates", "DISCONNECTED CONNECTING CONNECTED")
DISCONNECTED, CONNECTING, CONNECTED = (NodeCnxnStates.DISCONNECTED,
        NodeCnxnStates.CONNECTING, NodeCnxnStates.CONNECTED)


# NodeInfoKeys enum members have their associated ASCII key as member.value
class NodeInfoKeys(Enum):
    MAX_VERSION = b'max_version'
    LISTEN_PORT = b'listen_port'
    NODE_KEY = b'node_key'
    IDS = b'ids'
MAX_VERSION, LISTEN_PORT, NODE_KEY, IDS = (NodeInfoKeys.MAX_VERSION,
        NodeInfoKeys.LISTEN_PORT, NodeInfoKeys.NODE_KEY, NodeInfoKeys.IDS)


# IDCheckPriorities allows prioritization of hash computation for different
# node IDs. It is IntEnum so that we can do numeric comparisons on different
# priority values. This allows them to be used unadorned in the hasher's
# priority queue heap.
IDCheckPriorities = IntEnum("IDCheckPriorities", "CRITICAL HIGH MEDIUM LOW UNSET")
CRITICAL, HIGH, MEDIUM, LOW, UNSET = (IDCheckPriorities.CRITICAL,
        IDCheckPriorities.HIGH, IDCheckPriorities.MEDIUM,
        IDCheckPriorities.LOW, IDCheckPriorities.UNSET)
