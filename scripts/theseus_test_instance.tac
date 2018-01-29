from twisted.application.service import Application
from twisted.internet.address import IPv4Address
#from twisted.internet import reactor

from theseus.nodemanager import NodeManagerService

import random


application = Application("theseus")

manager = NodeManagerService()
manager.setServiceParent(application)

with open("/tmp/instances/ports") as f:
    for line in f:
        if len(line.strip()) == 0:
            continue
        port, key = line.strip().split(" ", 1)

        addr = IPv4Address("TCP", "127.0.0.1", int(port))

        for node in manager:
            if random.random() > 0.5:
                node.connect(addr, eval(key))

# TODO add lookups which fire after various time delays (via reactor.callLater?)
