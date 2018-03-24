#from enum import Enum, IntEnum
from ..enums import NodeStateKeys, NoiseProtoRoles, NodeCnxnStates, NodeInfoKeys, IDCheckPriorities


#NodeStateKeys: Enum
ROLE: NodeStateKeys
STATE: NodeStateKeys
LAST_ACTIVE: NodeStateKeys
INFO: NodeStateKeys
CNXN: NodeStateKeys

#NoiseProtoRoles: Enum
INITIATOR: NoiseProtoRoles
RESPONDER: NoiseProtoRoles

#NodeCnxnStates: Enum
DISCONNECTED: NodeCnxnStates
CONNECTING: NodeCnxnStates
CONNECTED: NodeCnxnStates

#NodeInfoKeys: Enum
MAX_VERSION: NodeInfoKeys
LISTEN_PORT: NodeInfoKeys
ID: NodeInfoKeys

#IDCheckPriorities: IntEnum
CRITICAL: IDCheckPriorities
HIGH: IDCheckPriorities
MEDIUM: IDCheckPriorities
LOW: IDCheckPriorities
UNSET: IDCheckPriorities
