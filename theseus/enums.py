from enum import Enum, IntEnum


NodeStateKeys = Enum("NodeStateKeys", "ROLE STATE LAST_ACTIVE INFO CNXN")
ROLE, STATE, LAST_ACTIVE, INFO, CNXN = (NodeStateKeys.ROLE,
        NodeStateKeys.STATE, NodeStateKeys.LAST_ACTIVE, NodeStateKeys.INFO,
        NodeStateKeys.CNXN)

NoiseProtoRoles = Enum("NoiseProtoRoles", "INITIATOR RESPONDER")
INITIATOR, RESPONDER = NoiseProtoRoles.INITIATOR, NoiseProtoRoles.RESPONDER

NodeCnxnStates = Enum("NodeCnxnStates", "DISCONNECTED CONNECTING CONNECTED")
DISCONNECTED, CONNECTING, CONNECTED = (NodeCnxnStates.DISCONNECTED,
    NodeCnxnStates.CONNECTING, NodeCnxnStates.CONNECTED)

NodeInfoKeys = Enum("NodeInfoKeys", "ID LISTEN_PORT MAX_VERSION")
ID, LISTEN_PORT, MAX_VERSION = (NodeInfoKeys.ID, NodeInfoKeys.LISTEN_PORT,
        NodeInfoKeys.MAX_VERSION)

# IDCheckPriorities is IntEnum so that the priorities can be compared & thus
# used directly in the hasher's priority queue heap
IDCheckPriorities = IntEnum("IDCheckPriorities", "CRITICAL HIGH MEDIUM LOW UNSET")
CRITICAL, HIGH, MEDIUM, LOW, UNSET = (IDCheckPriorities.CRITICAL,
        IDCheckPriorities.HIGH, IDCheckPriorities.MEDIUM,
        IDCheckPriorities.LOW, IDCheckPriorities.UNSET)
