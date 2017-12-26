from enum import Enum


NodeStateKeys = Enum("NodeStateKeys", "ROLE")
ROLE = NodeStateKeys.ROLE

NodeInfoKeys = Enum("NodeInfoKeys", "ID LISTEN_PORT MAX_VERSION")
ID, LISTEN_PORT, MAX_VERSION = NodeInfoKeys.ID, NodeInfoKeys.LISTEN_PORT, NodeInfoKeys.MAX_VERSION

NoiseProtoRoles = Enum("NoiseProtoRoles", "INITIATOR RESPONDER")
INITIATOR, RESPONDER = NoiseProtoRoles.INITIATOR, NoiseProtoRoles.RESPONDER
