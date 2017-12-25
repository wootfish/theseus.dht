from enum import Enum


NodeStateKeys = Enum("NodeStateKeys", "ROLE")
ROLE = NodeStateKeys.ROLE

NoiseProtoRoles = Enum("NoiseProtoRoles", "INITIATOR RESPONDER")
INITIATOR, RESPONDER = NoiseProtoRoles.INITIATOR, NoiseProtoRoles.RESPONDER
