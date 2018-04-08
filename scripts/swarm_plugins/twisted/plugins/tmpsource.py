from twisted.plugin import IPlugin
from twisted.internet.defer import succeed

from zope.interface import implementer

from theseus.contactinfo import ContactInfo
from theseus.plugins import IPeerSource
from noise.functions import KeyPair25519

import os


@implementer(IPlugin, IPeerSource)
class TmpTracker:
    def get(self, paranoid=False):
        # disregard the paranoid flag since this is just a test over localhost
        l = []
        for fname in os.listdir("/tmp/theseus_ports/"):
            with open("/tmp/theseus_ports/" + fname, "rb") as f:
                key_bytes = f.read()
            key = KeyPair25519.from_public_bytes(key_bytes)
            l.append(ContactInfo("127.0.0.1", int(fname), key))
        return succeed(l)

    def put(self, contact_info, paranoid=False):
        if contact_info.port is None or contact_info.key is None:
            return

        with open("/tmp/theseus_ports/" + str(contact_info.port), "wb+") as f:
            f.write(contact_info.key.public.public_bytes())


tmp_tracker = TmpTracker()
