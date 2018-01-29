# Theseus DHT Protocol

The Theseus DHT is a distributed hash table with unusually strong security properties.

It is derived in large part from Kademlia, an efficient distributed hash table algorithm which is good at handling benign failures but bad at handling malicious interference. In particular, Kademlia is very vulnerable to Sybil attacks, which can result in the modification or erasure of any data in the network.

The Theseus DHT protocol addresses these and other concerns, mitigating Sybil attacks through a combination of several novel strategies. It also adds features like strong encryption, optional authentication, optional perfect forward secrecy, and more. The network's Sybil resistance also increases as the network itself grows.

To a passive observer, all Theseus DHT protocol traffic is indistinguishable from random noise. Even message lengths can be made to follow arbitrary patterns or no pattern at all. All this makes the protocol very hard to fingerprint. Any node which is able to get a trusted introduction to the network also enjoys considerable protection against man-in-the-middle attacks. Standard, well-studied cryptographic primitives are used throughout.

The Theseus DHT is being developed as a component of the overall Theseus project. Since the DHT's resistance to Sybil attacks increases as the network itself grows, the DHT is being developed as a stand-alone library which can be used by any program that wants to be able to use a simple, secure distributed hash table.

A nice privacy property: With multiple applications using the same DHT, a user's presence on the DHT indicates their use of one of these applications, but _doesn't indicate which one they're using_.

The larger the network gets, the more secure and reliable it is for everyone.


# Table of Contents

- [Specification](#specification)
  - [Transport](#transport)
  - [Encryption](#encryption)
    - [Initial Handshake](#initial-handshake)
    - [Subsequent Handshakes](#subsequent-handshakes)
    - [Message Sizes](#message-sizes)
    - [Plaintext Format](#plaintext-format)
  - [Storing Data](#storing-data)
    - [Tags](#tags)
  - [Node Addressing and Routing](#node-addressing-and-routing)
  - [KRPC](#krpc)
    - [Definitions](#definitions)
    - [Queries](#queries)
      - [`find`](#find)
      - [`get`](#get)
      - [`put`](#put)
      - [`info`](#info)
      - [`handshake_suggest`](#handshake-suggest)
      - [`handshake_request`](#handshake-request)
    - [Errors](#errors)
- [Terminology Reference](#terminology-reference)
- [Discussion](#discussion)
  - [Design Decisions](#design-decisions)
    - [Using TCP](#using-tcp)
    - [Choice of Ciphersuite](#choice-of-ciphersuite)
  - [Extending the Protocol](#extending-the-protocol)
    - [Adding New Data Tags](#adding-new-data-tags)
  - [Next Steps](#next-steps)


# Specification

## Transport

The Theseus DHT protocol uses TCP at the transport layer. This is one of the most significant ways in which we deviate from Kademlia, which specifies UDP. The move to a stateful, connection-based protocol adds some overhead but makes the cryptography much easier by providing reliability and ordered delivery. Some of the motivations for this decision are discussed [here](#using-tcp).

## Encryption

### High-Level Overview

Encryption of Theseus protocol messages is handled through the Noise Protocol Framework. The authoritative documentation for Noise can be found [here](https://noiseprotocol.org/noise.html), and the Python library we use is [here](https://github.com/plizonczyk/noiseprotocol).

All traffic is encrypted, and all encrypted messages are indistinguishable from random noise. Messages may be chunked to arbitrary sizes, and plaintexts may optionally be padded before encryption, further reducing fingerprintability.

### Initial Handshake

In order to avoid any fingerprintable protocol preamble, we will specify a default handshake pattern and ciphersuite: `Noise_NK_25519_ChaChaPoly_BLAKE2b`. The `NK` pattern here provides for an exchange of ephemeral public keys to establish an encrypted channel, and for authentication of the responder (using their node key). The initial ephemeral key must be encoded with [Elligator](https://elligator.cr.yp.to/) to keep it from being trivially fingerprintable.

    (TODO: figure out how to get Elligator support with the Python Noise library we're using -- might have to roll our own and shim it in at the protocol object level)

### Subsequent Handshakes

After the initial handshake and establishment of the encrypted channel, additional handshakes may be performed. These are negotiated through RPC queries and responses. Once the peers agree on parameters like the handshake pattern and the public keys to be used for authentication, they may discard their current `CipherState` objects and, within the same TCP connection, start from scratch executing a new handshake. In order for the new handshake's session to inherit the security properties of the old session, a PSK must be negotiated within the old session and included in the new handshake via the `psk0` modifier. Specifics for that process are given in [the specification for the `handshake_request` RPC below](#handshake-request).

The handshake patterns which may be used are `NNpsk0`, `KNpsk0`, `NKpsk0`, `KKpsk0`.

The pattern may use any supported curve, cipher, or hash function. Wherever possible, the default choices of `Curve25519`, `ChaChaPoly`, and `BLAKE2b` should be favored. These defaults may change, though this will probably only happen if cryptographic weaknesses in any of them are discovered.

If for some reason two peers don't want to use a PSK, i.e. if they want to restart their Noise session from scratch, then rather than re-hanshaking they should just close and re-open their connection.

### Message Sizes

Every encrypted Theseus protocol message is preceded by an encrypted declaration of the protocol message's size. Whenever a plaintext is ready to send, the plaintext bytestring's length is calculated, encoded as a big-endian 32-bit integer, and encrypted, yielding a 20-byte ciphertext (4 message bytes + 16 AE tag bytes). This encrypted length announcement is sent, then the plaintext is encrypted and sent.

The process for receiving higher-level protocol messages is therefore essentially this:

1. Read bytes off the wire until we've received 20 bytes total.
2. Decrypt these 20 bytes and treat the resulting 4 bytes as an unsigned, big-endian 32-bit integer N.
3. Read bytes off the wire until we've received N + 16 more bytes total.
4. Decrypt these N + 16 bytes. This is the protocol message.
5. Repeat.

This scheme allows the size of every ciphertext to be known in advance, which in turn allows arbitrary message chunking without risk of ambiguity regarding message boundaries. Thus, individual packets sent across the wire can be arbitrarily sized, and thus the protocol can assume essentially any traffic pattern.

It's probably worth noting that this scheme creates a theoretical limit on the size of Theseus protocol messages: 2<sup>32</sup> - 1 = 4,294,967,295 bytes. That's 4 GiB, so any application running up against this limit has probably made some big mistakes along the way, to the point where the size limit is the least of their concerns.

In environments which aren't likely to have 4 GiB of RAM to spare at any given moment, applications are encouraged to set smaller internal limits on message size -- maybe 2<sup>20</sup> bytes or so. This suggestion, while much smaller, is still conservatively large as a sort of future-proofing. Theseus DHT protocol traffic will probably never even come close to this limit. Individual Noise protocol messages are capped at 65535=2<sup>16</sup>-1 bytes of ciphertext, so protocol messages exceeding 65535 - 16 = 65519 bytes of plaintext will of course need to be sent in chunks.

### Plaintext Format

Each message starts with the RPC embedded in a netstring. Anything after the end of the netstring is discarded. Thus any message may contain arbitrary amounts of padding, or no padding at all.

## Storing Data

The DHT is capable of storing arbitrary data at arbitrary 160-bit (20-byte) addresses. Stored data will be returned to queriers as a bencoded list of entries. Users wishing to store raw binary data may do so by encapsulating their data within a bencoded bytestring.

Some DHTs give their users less flexibility than this. For instance, Mainline DHT's `announce_peer` query includes a `port` field but not an IP address field. The IP address is auto-populated by the query recipient.

There are two main reasons for this: First, the receiving node already has this information -- it's right there in the query packet header -- and so including it in the RPC would be redundant. Preventing querying nodes from providing the IP address information also means that nodes have a much harder time submitting an `announce_peer` query for anyone other than themselves. This cuts down on garbage data and makes it more difficult to abuse Mainline DHT for e.g. traffic amplification.

In order to provide both the flexibility of arbitrary data storage and the benefits of more restrictive protocols like Mainline DHT, the Theseus DHT provides the option to request "tags" on submitted data, and to request only data matching a given tag. These tags are populated by the storing node based on public information available to it.

So, for instance, to duplicate Mainline DHT's `announce_peer` functionality you could submit a datum indicating a port you're listening on, and request that it be tagged with your public IP. Or you could submit an empty datum and have the remote node tag it with both your IP and port.

### Tags

Tags are specified via a `tags` argument within individual RPCs. Nodes should implement all specified tags. If a node receives a request to populate tags it doesn't recognize, the node should respond with error 203 [as specified below](#errors).

The only specified tags at this time are `ip` and `port`. The topic of adding additional tags is discussed at some length below.

    (TODO: fill out the actual section discussing this)

## Node Addressing and Routing

Every node has an address in the DHT network. Addresses are 20 bytes long. The "distance" between two nodes is the integer result of the XOR of their addresses. This all is as in Kademlia.

The proper operation of the DHT relies on addresses being uniformly distributed and nodes being unable to choose their own addresses. To achieve this, we allow nodes to choose their *ID preimage*, and derive their actual node IDs from a cryptographic hash of this preimage.

The hash function used is Argon2id. This is a state-of-the-art memory-hard hash function usually used for hashing passwords. It is designed to make parallelized brute-force search of the input space as difficult as possible. The work parameters we will use are memlimit=2<sup>28</sup> and opslimit=3 (these are the values of the PyNaCl library constants MEMLIMIT\_MODERATE and OPSLIMIT\_MODERATE, respectively).

Nodes should maintain a routing table operating as defined in Kademlia and BEP-5. If one peer is running multiple nodes, it may share a routing table between them. This would reduce overhead and also likely improve the quality of routing table query results. If a routing table is shared between multiple nodes, it should perform bucket splits when *any* of nodes' IDs fall into a given bucket, rather than performing them only when the inserting node's ID does.

## KRPC

### Definitions

The protocol is realized through a set of bencoded RPC messages following the KRPC format, as described by the Mainline DHT implementation of Kademlia. BEP-05 defines the KRPC format as follows:

> There are three message types: query, response, and error. ... A KRPC message is a single dictionary with two keys common to every message and additional keys depending on the type of message. Every message has a key "t" with a string value representing a transaction ID. This transaction ID is generated by the querying node and is echoed in the response, so responses may be correlated with multiple queries to the same node. The transaction ID should be encoded as a short string of binary numbers, typically 2 characters are enough as they cover 2^16 outstanding queries. The other key contained in every KRPC message is "y" with a single character value describing the type of message. The value of the "y" key is one of "q" for query, "r" for response, or "e" for error. 

We define the following queries: `find`, `get`, `put`, `info`, `handshake_suggest`, and `handshake_request`. These deal with looking up nodes, storing data on nodes, retrieving data from nodes, exchanging node metadata, and negotiating and finalizing re-handshake parameters, respectively.

### Contact Format

A node's contact information may be encoded as a bytestring of length 58. This is the concatenation, in order, of:

- The node's ID (20 bytes)
- The node's IP address (4 bytes)
- The node's port (2 bytes)
- The node's Ed25519 'node key' (32 bytes)

Network byte order should be used for all fields. Sharing contact info for multiple nodes is as simple as concatenating the contact info of each individual node, producing a bytestring whose length is a multiple of 58.

### Queries

#### `find`

This is essentially analogous to Kademlia's `find_node` query. Takes a target DHT address as an argument. The queried node returns the closest nodes to that target in its routing table.

Arguments: `{"addr": "<160-bit address>"}`

Response: `{"nodes": "<compact node info>"}`

#### `get`

Try to retrieve data from a node. Takes a DHT address as an argument. The response differs based on whether the queried node has stored data for that address. If it does, it returns the data. If it doesn't, it just returns routing suggestions like with `find_node`.

There is an optional argument, `tags`, which should map to a (possibly empty) list. If `tags` is included, only data with at least the tags listed will be returned. Queries lacking `tags` are taken as implicitly requesting only untagged data; queries mapping `tags` to `[]` request both tagged and untagged data.

Arguments: `{"addr": "<160-bit address>", "tags": []}`

Response:
- `{"data": <arbitrary data type>}`
- or `{"nodes": "<compact node info>"}`

#### `put`

For this query we specify an optional key, `sybil`, which keys to an integer value of 1 or 0 depending on whether the sending node believes a vertical Sybil attack is taking place at the write address. If `sybil` is present and nonzero, the receiving node may attempt to verify the claim and subsequently increase its timeout for stored data. The `sybil` key may be omitted, but this should only be done if the sending node doesn't have enough info to determine whether a Sybil attack is underway. Methodology for detecting vertical Sybil attacks is described below.

The putter may request that certain tags be applied to the data via the `tags` argument.

The response is an empty dictionary. This should of course still be sent, in order to acknowledge query receipt.

Arguments: `{"addr": "<160-bit address>", "data": <arbitrary data>, "tags": [], "sybil": <0 or 1>}`

Response: `{}`

#### `info`

Used for metadata exchange between peers. The reply contains a dictionary encoding information such as the remote node's ID, version info, and so on.

By default, all available data is returned. The querying peer may limit the data returned by including the optional `keys` argument in their query and providing a comprehensive list of keys desired. This prevents large data like Bloom filters from being transmitted unnecessarily. The querying peer may also report that its own info has changed (such as would happen when a node changes ID or when files are added to its cache) by including an optional `advertise` key.

A query like `"{advertise": {"id": ["<querying node's id>", "<querying node's id preimage>"]}, "keys": ["id"]}` allows two nodes to exchange ID information in one round trip.

Submitting a query with `keys` included and mapped to an empty list is allowed. The reply's `info` key should map to an empty dictionary.

Note that the `values` associated with keys within the `info` dictionary may be arbitrary bencoded data, even though the example below only shows strings. It is perfectly fine to include a set of flags as a binary string, to include nested lists or dictionaries, etc.

A node may have as many info fields as it wants. It should at the very minimum provide these: `{"id": ["<160-bit node id>", "<node id hash preimage>"], "listen_port": <port node is listening for cnxns on (int)>, "max_version": "protocol version string"}`.

Applications using the Theseus DHT may feel free to add their own metadata keys, and are encouraged to use a uniform and unusual prefix for these keys to avoid naming conflicts. For instance, Theseus-specific parameters like Bloom filters for search are prefixed `theseus_`.

Arguments: `{"info": {"sender_key_one": "sender_value_one", ...}, "keys": ["key_one", "key_two", ..., "key_n"]}`

Response: `{"info": {"key_one": "value_one", "key_two": "value_two", ... , "key_n": "value_n"}}`

#### `handshake_suggest`

Messages of this type are purely informational and may be exchanged any number of times between handshakes. Their purpose is to communicate re-handshake parameters that the sending party would find acceptable.

The following parameters need to be established:

The `initiator` argument should map to 1, i.e. True, if the querier wishes to play the role of initiator in the new handshake, and 0, i.e. False, if they wish to be the responder.

The `handshake` argument specifies the full Noise protocol name for the new handshake to be performed. Rules for handshake parameters are outlined in the ["Subsequent Handshakes"](#subsequent-handshakes) section above.

If the Noise handshake pattern is `KNpsk0` or `KKpsk0`, then the `initiator_s` argument should be present and should map to a static public key to be used by the initiator.

If the Noise handshake pattern is `NKpsk0` or `KKpsk0`, then the `responder_s` argument should be present and should map to a static public key to be used by the responder.

Arguments: `{"initiator": 1, "handshake": "Noise_KK_25519_ChaChaPoly_BLAKE2b", "initiator_s": "<32-byte Curve25519 public key>", "responder_s": "<32-byte Curve25519 public key>"}`

Response: `{}`

#### `handshake_request`

Messages of this type specify concrete re-handshake parameters. If the remote node finds these parameters unacceptable, it may reply with an error code. A non-error response indicates that the remote node accepts the re-handshake parameters.

After sending a non-error response, the responder should immediately enter the new handshake. Likewise for the receiver, who should immediately enter the handshake after receiving such a response.

The arguments `initiator`, `handshake`, `initiator_s`, and `responder_s` are specified identically to the same-named arguments for `handshake_suggest`.

The argument `psk` should be included in both the query and response. In each case it should map to a bytestring of arbitrary contents. It is strongly suggested that these contents be a random string of length equal to the output size of the hash function specified in the `handshake` argument.

The values of both the query and response's `psk` arguments are to be hashed using the `handshake` argument's specified hash function. Their hashes are then to be XORed and the resulting value used as a PSK for the new handshake (applied via the psk0 Noise protocol modifier).

Arguments: `{"initiator": 1, "handshake": "Noise_KK_25519_ChaChaPoly_BLAKE2b", "initiator_s": "<32-byte Curve25519 public key>", "responder_s": "<32-byte Curve25519 public key>", "psk": "<bytestring>"}`

Response: `{"psk": "<bytestring>"}`

### Errors

Errors at the KRPC level are prefixed 1xx. Errors at the Theseus DHT protocol level are prefixed 2xx. Errors at higher levels of abstraction are prefixed 3xx.

So far, the following error codes are defined:

- `1xx` level:
  - `100: Invalid KRPC message`
  - `101: Internal error`
- `2xx` level:
  - `200: Invalid DHT protocol message`
  - `201: Internal error`
  - `202: Method not recognized`
  - `203: Tag not recognized`
- `3xx` level:
  - `300: Generic error`
  - `301: Rate-limiting active`

# Terminology Reference

- `Distributed hash table`: A key-value store collectively maintained by a group of networked computers. The data structure persists even as individual users join or leave the network. Usually shortened to `DHT`.
- `Kademlia`: An efficient distributed hash table protocol which operates over UDP. Used by Mainline DHT and many others. Simple, powerful, and exceptionally amenable to mathematical analysis. Vulnerable to Sybil attacks. More info [here](https://en.wikipedia.org/wiki/Kademlia). The Theseus DHT protocol is derived in part from Kademlia.
- `Node`: An individual entity on the DHT network. A user may operate as many nodes as they like. The more nodes there are in the network, the more resilient it is to several categories of attack, including Sybil attacks.
- `Peer`: A user, who may be operating one or more nodes on the network, and who may be running other network-facing software as well (such as e.g. a torrent client). Alternately, the sum total of the network-facing software on a given system.
- `Ephemeral key`: A public key generated and transmitted at the start of a connection. Conveys no identity data whatsoever.
- `Node key`: A public key generated at node startup and transmitted along with a node's contact info. This key should persist for as long as a node is listening on the associated address and port. Used to provide some resistance against man-in-the-middle attacks. More info [here](http://sohliloquies.blogspot.fr/2017/06/transient-public-keys-for-resisting.html).
- `Noise protocol framework`: A modern, flexible, well-documented framework for crypto protocols. More info [here](http://noiseprotocol.org/noise.html).
- `Elligator`: An encoding system which renders elliptic curve points indistinguishable from uniform random strings. The handshakes used by the Theseus DHT protocol begin with ephemeral public keys; under normal circumstances these keys are trivial for a passive observer to identify, but with an encoding scheme like Elligator they share the rest of the traffic's indistinguishability from random noise.
- `BEP-5`: "BitTorrent Enhancement Proposal 5", the specification document for Mainline DHT. See [here](http://www.bittorrent.org/beps/bep_0005.html).

# Discussion

## Design Decisions

### Using TCP

The choice to use TCP rather than UDP is a significant one and is not taken lightly. The essential motivation is that it simplifies the cryptography. For an idea of why, see [here](https://noiseprotocol.org/noise.html#out-of-order-transport-messages). Note in particular that including plaintext nonce values with messages would break our requirement that *all* protocol traffic be indistinguishable from random noise. Persistent connections also provide a convenient abstraction within which to perform multiple consecutive handshakes.

One complication: A TCP connection to a specific port will originate from an arbitrary 'ephemeral' port on the part of the connector. UDP can operate this way but doesn't have to, because it's connectionless. Thus protocols like Kademlia which operate over UDP can and do use their packets' source port to advertise the port they're listening for messages on -- a trick we can't use if our connections have to originate from ephemeral ports. Compensating for this requires provisions at the protocol level for communicating the port we're listening for connections on. This is why `listen_port` is a required datum in the `info` query.

A big issue here that we'll want to spend some time looking hard at once the reference implementation is otherwise mature and stable: NAT traversal. We may be able to work out a scheme for reachable nodes to perform some sort of hole punching to help NATed hosts to reach each other.

If hole punching doesn't pan out, another interesting possibility (which was touched on briefly in some of the Theseus blog posts back on Sohliloquies) would be to see if the network can support an onion routing overlay, and if so, whether it'd be viable for NATed hosts to make themselves available as "hidden services" served from other, publicly accessible hosts. This would also have other benefits for users willing or needing to trade performance for privacy -- but that's a story for another day.

### Choice of Ciphersuite

The default algorithm choices specified above were selected to provide as conservative and robust of a default configuration as possible. The only arguable exception is Curve25519, which, while still a fairly conservative choice, is still less so than Curve448. The deciding factor in this case was that the crypto libraries we're using provide good implementations of Curve25519, whereas Curve448 support comes from some native Python which is pretty much guaranteed not to be as well hardened against say side-channel or timing attacks. I'm totally willing to revisit this if we can get nice Curve448 bindings, maybe via OpenSSL or something.

Argon2id was chosen over my earlier favored algorithm, bcrypt, due to its state-of-the-art design and memory-hardness. Bcrypt is a great piece of work which has stood the test of time exceptionally well, but by nature of being CPU-hard rather than memory-hard it is less costly to mount massively parallel attacks on bcrypt using e.g. FPGAs. The memory overhead required for background verification of Argon2id hashes on a user's machine is also likely to be less impactful on performance than the CPU overhead required to verify bcrypt hashes of comparable hardness.

BLAKE2b is favored over SHA512 because it is faster, based on a more modern and robust construction (no length-extension attacks!), and doesn't suffer from any ominous reduced-round preimage resistance breaks like the SHA-2 family has. SHA512 still seems secure enough for the time being, of course, but if I had to bet on which algorithm I think'll be looking better 5 or 10 years from now, I'd bet on BLAKE2b.

## Extending the Protocol

For now, let's just use GitHub issues for discussing potential protocol extensions. We'll probably want to come up with something better down the road, but we can worry about that then.

If you want to discuss anything privately, you can reach me (Eli) a couple different ways:
- Email: {my first and last name, no punctuation} at gmail.
- [Twitter](#https://twitter.com/elisohl): my DMs are open.

## Next Steps

- Implementation!

- Interesting question: The Noise Protocol Framework has the concept of a "fallback pattern", which allows graceful handling of situations where one party is not able to complete a handshake as desired by the other. It would be worth looking into whether we can securely integrate these patterns into the Theseus DHT protocol.
  - This is easier said than done. We have to be careful to avoid unnecessarily weakening the protocol against MitM attacks in the case of fallback protocols involving node keys. There will probably turn out to be a trade-off here, and it will have to be carefully considered.
  - Remember that a MitM attacker could trivially force a fallback handshake by just corrupting some transmitted data.
  - On the other hand, the benefits for people running long-lived nodes at static addresses also need to be considered. Supporting fallback could allow them to periodically rotate node keys and/or recover from key compromise without remote peers having to update their contact info for the nodes.
