# Overview

This library implements a Theseus DHT client as a Twisted service.

Applications built on the Twisted service architecture can straightforwardly
integrate Theseus DHT support by adding an instance of `PeerService` to their
top-level application. This service provides a high-level API which can be used
to get or put data in the DHT.

Twisted-based peer-to-peer applications wishing to build off the Theseus DHT
may integrate tightly with this library in order to extend and generalize its
functionality.

Applications not built on Twisted, like those using Python 3's asyncio, can
integrate in a few ways.
[This](https://meejah.ca/blog/python3-twisted-and-asyncio) blog post might be
helpful as a reference.

The Theseus protocol and this Theseus DHT client are both designed to be easily
extensible so that distributed applications requiring a reliable DHT construct
can easily be built on top of Theseus.


# Configuration

By default, Theseus creates and populates a configuration directory for itself.
The default config file contains sensible defaults for most fields. Someday
there may be be a clean option to override this config. In the meantime you can
always rebind `theseus.config.config` before instantiating PeerService.

Applications can use `theseus.config` to keep track of their own persistent
configuration as well, if they want, though they should be careful to avoid
name collisions.


# Peer-Level API

`PeerService` provides the following simple API for external use. These are
high-level methods designed to make sensible usage patterns easy by abstracting
away certain aspects of the underlying DHT.

The first two methods are concerned with DHT functions specifically, whereas
the rest are more geared towards constructing overlay networks on top of the
DHT peer swarm.

`PeerService` possesses other methods beyond the ones listed here, but these
are only exposed because Python lacks a way to make them private. Any method
not listed here is not intended for external use.


### `dht_get(key, redundancy=1)`

Returns a list of `bytes`.

`key: AnyStr` The key to get data for. May be of any length. The DHT address or
addresses to retrieve will be determined by hashing this key.

`redundancy: int` The redundancy factor to use. Only values between 1 and 5
will be accepted. The default value of 1 is usually best; higher values will
lead to slower lookups but will fare better against Sybil attacks.

### `dht_put(key, value, redundancy=1, encoding='UTF-8')`

Returns an `int` listing the data's estimated lifespan in the DHT.

`key: AnyStr` The key to store data at. May be of any length. The DHT address
or addresses to store `value` at will be determined by hashing this key.

`value: AnyStr` The value to store. If given as `str`, it will be encoded to
`bytes` using `encoding`.

`redundancy: int` The redundancy factor to use. Only values between 1 and 5
will be accepted. The default value of 1 is usually best; higher values will
lead to slower lookups but will fare better against Sybil attacks.

`encoding: str` If you pass `str`s to `value`, they will be encoded using
`encoding`.


### `make_cnxn(contact_info)`

For use with peer-to-peer applications wanting to create their own connections
to DHT peers, for instance to create overlay networks within the DHT network.
Using this method ensures full RPC support in all connections and prevents
redundant connections from being made (if a connection to the peer specified by
`contact_info` already exists, the corresponding protocol object is returned).

`contact_info: theseus.ContactInfo` The remote peer to connect to.

Returns a `Deferred` which will fire with a DHTProtocol (or subclass) on
success, or a Failure on failure.


### `add_to_blacklist(host)`

Adds a given host to the blacklist. This will prevent any new connections to
the host from being made. `TODO: Also terminate existing cnxns, if any.`

`host` is as in `theseus.ContactInfo.host`. Currently this is just an IPv4
address, though that may change.

Returns `None`.


# Integrations

## Note: Twisted Plugins

Most close integrations between Theseus and external programs are mediated
through Twisted Plugins.
[This](https://twistedmatrix.com/documents/current/core/howto/plugin.html) page
describes how the plugin system works.

Essentially, a set of _plugin interfaces_ are provided by Theseus. You can
modify Theseus's behavior by implementing any of these interfaces and making
your implementations available to Twisted in any of the ways described
[here](https://twistedmatrix.com/documents/current/core/howto/plugin.html#extending-an-existing-program).


## Adding KRPCs

The plugin interface for this is `theseus.plugins.IKRPC`. These plugins are
enumerated by KRPCProtocol during \_\_init\_\_.

KRPCs may also be added by subclassing DHTProtocol and modifying PeerTracker to
create instances of your subclass. For complex KRPCs or those with tight
integrations into other Theseus subsystems, this may be the better option.

Subclassing DHTProtocol is also the only way to override the query and response
handlers populated by DHTProtocol, although in the course of ordinary use
_overriding these handlers is not recommended._

To correctly subclass DHTProtocol and register your subclass for use with new
connections:

* Create a subclass, and in it override \_\_init\_\_ in the same manner as
  `DHTProtocol.__init__`, making sure to update `self.query_handlers` (and
  possibly also `self.response_handlers`) with handlers for your new KRPCs.

* After your subclass is defined, set `PeerTracker.protocol` to point to it.

All connections started after `PeerTracker.protocol` is reassigned will use
your new protocol and will support your new KRPCs.


## Adding `info` Keys

The plugin interface for this is `theseus.plugins.IInfoProvider`. For a sample
implementation, see `theseus/twisted/plugins/info.py`.


## Adding Peer Sources

These sources are queried on startup to provide the local peer with an
introduction to the peer swarm.

The plugin interface for this is `theseus.plugins.IPeerSource`. For a sample
implementation, see `scripts/twisted/plugins/tmpsource.py`.


# Notes

[preferred style (TODO)](https://twistedmatrix.com/documents/current/api/twisted.internet.defer.html#inlineCallbacks)
