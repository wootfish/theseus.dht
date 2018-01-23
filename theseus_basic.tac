from twisted.application.service import Application
from theseus.nodemanager import NodeManagerService

application = Application("theseus")

backend = NodeManagerService()
backend.setServiceParent(application)
