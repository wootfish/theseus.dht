from enum import Enum


NodeStateKeys = Enum("NodeStateKeys", "ROLE STATE LAST_ACTIVE INFO CNXN")
ROLE, STATE, LAST_ACTIVE, INFO, CNXN = (NodeStateKeys.ROLE,
        NodeStateKeys.STATE, NodeStateKeys.LAST_ACTIVE, NodeStateKeys.INFO,
        NodeStateKeys.CNXN)

NoiseProtoRoles = Enum("NoiseProtoRoles", "INITIATOR RESPONDER")
INITIATOR, RESPONDER = NoiseProtoRoles.INITIATOR, NoiseProtoRoles.RESPONDER

NodeCnxnStates = ENUM("NodeCnxnStates", "DISCONNECTED CONNECTING CONNECTED")
DISCONNECTED, CONNECTING, CONNECTED = (NodeCnxnStates.DISCONNECTED,
    NodeCnxnStates.CONNECTING, NodeCnxnStates.CONNECTED)

NodeInfoKeys = Enum("NodeInfoKeys", "ID LISTEN_PORT MAX_VERSION")
ID, LISTEN_PORT, MAX_VERSION = (NodeInfoKeys.ID, NodeInfoKeys.LISTEN_PORT,
        NodeInfoKeys.MAX_VERSION)