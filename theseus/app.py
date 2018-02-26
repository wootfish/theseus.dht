from twisted.application.service import Application
from theseus.nodemanager import NodeManagerService

application = Application("theseus_dht")

peer = PeerService()
peer.setName("peer")
peer.setServiceParent(application)
