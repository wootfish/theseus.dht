from twisted.application.service import Application

from theseus.peer import PeerService


application = Application("theseus_dht")

peer = PeerService()
peer.setName("peer")
peer.setServiceParent(application)
