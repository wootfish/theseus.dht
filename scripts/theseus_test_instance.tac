from twisted.application.service import Application
#from twisted.internet import reactor

from theseus.nodemanager import NodeManagerService


# set up application
application = Application("theseus")

manager = NodeManagerService()
manager.setServiceParent(application)

# TODO feed contact infos to nodes in manager
# TODO add lookups which fire after various time delays (via reactor.callLater?)
