from zope.interface import Interface, Attribute


class IPeerSource(Interface):
    """
    Interface for plugins that provide additional sources of peers. These will
    be aggregated and queried on startup, and possibly at later points as well.
    """

    def get(paranoid):
        """
        Gets a list of peers.

        The 'paranoid' parameter, if set to True, specifies that active
        network-level malicious interference should be assumed. This means that
        peer retrieval methods which are not secure against, say,
        man-in-the-middle attacks, should not be performed.

        For instance, a request to an HTTPS peer source should be performed
        whether paranoid is True or False. An HTTP peer source, however, should
        only be queried if paranoid=False, and should provide an empty list if
        paranoid=True.

        This is because HTTPS provides strong security against network-level
        adversaries, while HTTP does not.

        More detailed discussion on this point and on threat modeling more
        generally is forthcoming.

        The return type should be a Deferred which will fire with a list of
        ContactInfo objects.
        """

    def put(contact_info, paranoid):
        """
        Reports the local contact info to the remote peer. If the PeerSource
        this object represents does not accept remote submission, this function
        should just immediately return.

        The contact_info parameter should be a ContactInfo object specifying
        the local address. Any fields not required should be left as None. For
        instance, contact_info.host=None is fine if, say, reporting to a remote
        server that doesn't let you report your own IP but rather looks at the
        IP header on your reporting message and stores that.

        The paranoid parameter is as for get().

        This function should return None. (TODO: or should it return a Deferred
        that fires with None on completion?)

        FIXME: how should we generalize this to support e.g. reporting contact
        info for Tor hidden services?
        """


class IInfoProvider(Interface):
    """
    Interface for plugins that add support for extra peer info keys.
    """

    provided = Attribute(
            """
            An object enumerating the supported info keys. Technically only
            needs to support __contains__.
            """
            )

    def get(key):
        """
        Returns the value associated with the given info key. This will only be
        invoked with keys for which the 'contains' attribute reports support.
        """
