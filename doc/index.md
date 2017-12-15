# Theseus DHT Protocol

The Theseus DHT is a distributed hash table with unusually strong security properties.

It is derived in large part from Kademlia, an efficient distributed hash table algorithm which is good at handling benign failures but bad at handling malicious interference. In particular, Kademlia is very vulnerable to Sybil attacks, which can result in the modification or erasure of arbitrary data in the network.

The Theseus DHT protocol addresses these and other concerns, mitigating Sybil attacks through a combination of several novel strategies. It also adds features like strong encryption, optional authentication, optional perfect forward secrecy, and more. The network's Sybil resistance also increases as the network itself grows.

To a passive observer, all Theseus DHT protocol traffic is indistinguishable from random noise. Even message lengths can be made to follow arbitrary patterns or no pattern. All this makes the protocol very hard to fingerprint. Any node which is able to get a trusted introduction to the network also enjoys considerable protection against man-in-the-middle attacks. Standard, well-studied cryptographic primitives are used throughout, and the specific ciphersuites used are configurable.

The Theseus DHT is being developed as a component of the overall Theseus project. Since the DHT's resilience to Sybil attacks increases as the network gets bigger, this DHT component is being made separately available so that it may be integrated into any other apps which want a DHT providing these features. Support for per-app namespacing is included, to help the DHT scale well if it sees widespread adoption. The larger the network gets, the better and more secure it is for everyone.

# Table of Contents

- [Specification](#specification)
  - [Transport](#transport)
  - [Encryption](#encryption)
    - [Initial Handshake](#initial-handshake)
    - [Subsequent Handshakes](#subsequent-handshakes)
    - [Declaring Message Sizes](#declaring-message-sizes)
    - [Plaintext Format](#plaintext-format)
  - [KRPC](#krpc)
    - [Definitions](#definitions)
    - [Queries](#queries)
      - [find_node](#find_node)
      - [get_data](#get_data)
      - [put_data](#put_data)
      - [get_info](#get_info)
    - [Data Types](#data-types)
      - [`peers` Data Type](#peers-data-type)
        - [Query Data Format](#query-data-format)
        - [Response Data Format](#response-data-format)


# Specification

## Transport

We deviate from Kademlia by using TCP rather than UDP at the transport layer. The move to a stateful, connection-based protocol adds some overhead but makes the cryptography much easier by providing reliability and ordered delivery.

## Encryption

### Initial Handshake

Encryption is handled through the Noise Protocol Framework. This is what allows us to produce seemingly-random protocol traffic. The authoritative documentation for Noise can be found [here](https://noiseprotocol.org/noise.html), and the Python library we will use is [here](https://github.com/plizonczyk/noiseprotocol). In order to avoid any (fingerprintable) protocol preamble, we will specify a default handshake and ciphersuite: `Noise_NN_448_ChaChaPoly_SHA512`. The `NN` pattern here provides for an exchange of ephemeral public keys to establish an encrypted channel. The public keys should be Ellegator-encoded to keep them from being trivially fingerprintable.

    (TODO: make doubly sure using Elligator here is viable)

### Subsequent Handshakes

After the initial handshake and establishment of the encrypted channel, additional handshakes may be performed. These are negotiated through RPC queries and responses. Once the peers agree on parameters like the handshake pattern and the public keys to be used for authentication, they may discard their current `CipherState` objects and, within the same TCP connection, start from scratch executing a new handshake. In order for the new handshake's session to inherit the security properties of the old session, a PSK must be negotiated within the old session and included in the new handshake via the `psk0` modifier. Either or both parties may suggest a PSK. If multiple keys are chosen, the actual PSK used should be the result of XORing the keys' `SHA256` hashes.

The handshake patterns which may be used are `NNpsk0`, `KNpsk0`, `NKpsk0`, `KKpsk0`.

The pattern may use any supported curve, cipher, or hash function. Wherever possible, the default choices of `Curve448`, `ChaChaPoly`, and `SHA512` should be favored. These defaults may change if cryptographic weaknesses in any of the aforementioned primitives are discovered.

If for some reason two peers don't want to use a PSK, i.e. if they want to restart their Noise session from scratch, then rather than re-hanshaking they should just close and re-open their connection.

### Message Sizes

Every encrypted Theseus protocol message is preceded by an encrypted declaration of the protocol message's size. Whenever a plaintext is ready to send, the plaintext bytestring's length is encoded as a big-endian 32-bit integer and encrypted, yielding a 20-byte ciphertext (4 message bytes + 16 AE tag bytes). This is sent, then the plaintext is encrypted and sent. This scheme allows the size of every ciphertext to be known in advance, which in turn allows arbitrary message chunking without risk of ambiguity regarding message boundaries. Thus, individual packets sent across the wire can be arbitrarily sized, and can thus mimic essentially any traffic pattern.

It's worth noting that this scheme creates a theoretical limit on the size of Theseus protocol messages: 2<sup>32</sup> - 1 = 4,294,967,295 bytes. That's 4 GiB, so any application running up against this limit has probably made some big mistakes along the way, to the point where the size limit is almost certainly the least of their concerns.

In environments which aren't likely to have 4 GiB of RAM to spare at any given moment, applications are encouraged to set smaller internal limits on message size -- maybe 2<sup>20</sup> bytes or so. This suggestion, while much smaller, is still conservatively large as a sort of future-proofing. Theseus traffic will probably never even come close to this limit, except perhaps when exchanging uncompressed Bloom filters, and even then messages should fall comfortably short of the max size. Individual Noise protocol messages are capped at 65535 bytes of ciphertext, so Theseus protocol messages exceeding 65535 - 16 = 65519 bytes of plaintext will of course need to be sent in parts.

### Plaintext Format

To aid with traffic masking, any message may contain arbitrary amounts of padding (or no padding at all). Each message starts with the RPC encoded as a netstring. Anything after the end of the netstring is discarded. Padding must be included when calculating the length of the plaintext,

## KRPC

### Definitions

The protocol is conceptualized as a set of bencoded RPC messages following the KRPC protocol format as described by the Mainline DHT implementation of Kademlia, with a custom set of RPCs. BEP-05 defines the KRPC format as follows:

> There are three message types: query, response, and error. ... A KRPC message is a single dictionary with two keys common to every message and additional keys depending on the type of message. Every message has a key "t" with a string value representing a transaction ID. This transaction ID is generated by the querying node and is echoed in the response, so responses may be correlated with multiple queries to the same node. The transaction ID should be encoded as a short string of binary numbers, typically 2 characters are enough as they cover 2^16 outstanding queries. The other key contained in every KRPC message is "y" with a single character value describing the type of message. The value of the "y" key is one of "q" for query, "r" for response, or "e" for error. 

Note that we follow the MLDHT KRPC protocol as regards message _format_, but not as regards message _transport_.

We define the following queries: `find_node`, `get_data`, `announce_data`, and `get_info`.

## Queries

### `find_node`

Analogous to BEP-5's `find_node` query, though lacking an `id` key.

Arguments: `{"target": "<id of target node>"}`

Response: `{"nodes": "<compact node info>"}`

### `get_data`

Analogous to BEP-5's `get_peers`, but generalized to arbitrary data, not just peer tracking. A few example values for `type` are given in the next section. The response differs based on whether the queried node has stored data to return (if it doesn't, it just returns routing suggestions).

Arguments: `{"addr": "<20-byte DHT address for target data>", "type": "<data type>"}`

Response:
- `{"data": <arbitrary data type>}`
- or `{"nodes": "<compact node info>"}`

### `put_data`

For this query we specify an optional key, `sybil`, which keys to an integer value of 1 or 0 depending on whether the sending node believes a vertical Sybil attack is taking place at the write address. If `sybil` is present and nonzero, the receiving node may attempt to verify the claim and subsequently increase its timeout for stored data. The `sybil` key should be omitted if _and only if_ the sending node doesn't have enough statistical info to determine whether a Sybil attack is underway. If the receiving node finds no evidence of the claimed attack, it would be reasonable for it to blacklist the sending node. Methodology for detecting vertical Sybil attacks is described below.

The response is an empty dictionary. This should of course still be sent, in order to acknowledge query receipt.

Arguments: `{"type": "<data type>", "data": <arbitrary data type>}`

Response: `{}`

### `get_info`

Used to ask a remote peer to describe themself to the querying node. The reply contains a dictionary encoding information such as the remote node's ID, their local content Bloom filter, a protocol version or details on specific features they do or don't support, and so on.

By default, all available data is returned. The querying peer may limit the data returned by including the optional `keys` argument in their query and providing a comprehensive list of keys desired. This prevents large data like Bloom filters from being transmitted unnecessarily. The querying peer may also report that its own info has changed (such as would happen when a node changes ID or when files are added to its cache) by including an optional `advertise` key.

A query like `"{advertise": {"id": ["<querying node's id>", "<querying node's id preimage>"]}, "keys": ["id"]}` allows two nodes to exchange ID information in one round trip.

Submitting a query with `keys` included and mapped to an empty list is allowed. The reply's `info` key should map to an empty dictionary.

Note that the `values` associated with keys within the `info` dictionary may be arbitrary bencoded data, even though the example below only shows strings. It is perfectly fine to include a set of flags as a binary string, to include nested lists or dictionaries, etc.

For simplicity, there are no namespacing mechanisms here. Applications worried about avoiding naming conflicts should use a uniform and unusual prefix. Theseus-specific parameters like Bloom filters for search are prefixed `theseus_`.

A node may have as many info fields as it wants, but it should at the very minimum provide these: `{"id": ["<node's id>", "<id hash preimage>"], "max_version": "protocol version string"}`.

Arguments: `{"advertise": {"sender_key_one": "sender_value_one", ...}, "keys": ["key_one", "key_two", ..., "key_n"]}`

Response: `{"info": {"key_one": "value_one", "key_two": "value_two", ... , "key_n": "value_n"}}`

## Data Types

Any application using the Theseus DHT may define and store its own data types. The general idea is to have one type per application or major application function.

For instance, the full Theseus project will define and make use of a `theseus_sigs` data type, but that is outside the scope of this library.

Nodes are gently encouraged not to play favorites when it comes to setting timeouts for stored data of different types. Shortening timeouts based on _amount_ of data stored would, however, be reasonable in extreme cases. Correspondingly, while applications are encouraged to use the DHT, they are also encouraged to do whatever they can to minimize the amount of data they store in it, so as to lighten the load on their peers.

Only one data type is explicitly defined here: `peers`. It is included primarily to show by example how data types work and how to specify one.

### `peers` Data Type
