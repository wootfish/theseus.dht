from enum import Enum


NodeStateKeys = Enum("NodeStateKeys", "ROLE")
ROLE = NodeStateKeys.ROLE

NoiseProtoStates = Enum("NoiseProtoStates", "HANDSHAKE")
HANDSHAKE = NoiseProtoStates.HANDSHAKE

NoiseProtoRoles = Enum("NoiseProtoRoles", "INITIATOR RESPONDER")
INITIATOR, RESPONDER = NoiseProtoRoles.INITIATOR, NoiseProtoRoles.RESPONDER
