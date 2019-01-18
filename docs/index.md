# Theseus DHT Protocol

The Theseus DHT protocol lets you create distributed hash tables (DHTs) with unusually strong security properties.

Anyone can store data in the DHT and receive an estimate of how long that data will be stored. Once stored, data is very hard to remove or modify. Small data is stored longer; this makes the DHT well-suited for exchanging things like lists of peers, signed cryptographic hashes, compressed text, and so on.

Theseus DHT's routing is based on Kademlia, which is a simple, well-analyzed, and very efficient DHT protocol. Unfortunately, Kademlia suffers from several significant security setbacks. It is very vulnerable to Sybil attacks, which can result in the modification or erasure of any data in the network. It also uses no message encryption whatsoever. [Once upon a time, these may not have seemed like serious issues, but times are changing](https://wootfish.github.io/sohliloquies/2017/12/14/net-neutrality-and-theseus-dht.html).

Theseus DHT addresses these and other concerns, offering robustness in the face of Sybil attacks through [a combination of novel strategies](https://wootfish.github.io/sohliloquies/2017/02/26/resisting-sybil-attacks-in-distributed_25.html). It also adds new desirable features like strong encryption, optional authentication, optional perfect forward secrecy, resistance to man-in-the-middle attacks, and more. It runs over TCP, allowing it to be used with anonymity layers like Tor. The protocol's design permits easy mathematical analysis, allowing for rigorous proofs of its (considerable) resilience against Sybil attacks -- a property which increases in degree as the network itself grows.

To a passive observer, all Theseus DHT protocol traffic is indistinguishable from random noise. Not only that, but even message sizes can be made to follow arbitrary patterns or no pattern at all. All this is meant to make the protocol very hard to fingerprint. Any node which is able to get a trusted introduction to the network also enjoys considerable protection against active interference from malicious third parties (e.g. man-in-the-middle attacks). All cryptography is handled through the Noise Protocol Framework, which is [exceptionally well-designed and well-documented](http://noiseprotocol.org/noise.html). The protocol runs over TCP -- this means (among other things) that it can be used in conjunction with Tor.

The Theseus DHT is being developed as a component of the overall Theseus project. Since the DHT’s resistance to Sybil attacks increases as the network grows, the DHT is being developed as a stand-alone library. That way, it can also be used in any other application where a simple, secure distributed hash table is desired.

The Theseus DHT is designed to be very good at bootstrapping overlay networks, and to be easily extensible. For these reasons, building custom peer-to-peer applications on top of the Theseus DHT is trivial. A peer's presence on the DHT does not by itself indicate which DHT-based application they're using (unless they choose to disclose that). This is a nice privacy property to have. On top of that, the more users the DHT gets, the more resilient and reliable it is for everyone.


# Table of Contents

- [Specification](#specification)
  - [Brief Summary](#brief-summary)
  - [KRPC Format](#rpc-format)
  - [RPCs](#rpcs)
    - [`find`](#find)
    - [`get`](#get)
    - [`put`](#put)
    - [`info`](#info)
    - [`hs_suggest`](#hs_suggest)
    - [`hs_request`](#hs_request)
  - [Errors](#errors)
  - [Data Formats](#data-formats)
  - [Required Keys](#required-keys)
  - [Routing](#routing)
  - [Address Selection](#address-selection)
  - [Data Tags](#data-tags)
  - [Storage Durations](#storage-durations)
  - [Encryption](#encryption)
    - [High-Level Overview](#high-level-overview)
    - [Initial Handshake](#initial-handshake)
    - [Subsequent Handshakes](#subsequent-handshakes)
    - [Message Sizes](#message-sizes)
    - [Plaintext Format](#plaintext-format)
- [Brief Discussion](#brief-discussion)
  - [Peers and Nodes](#peers-and-nodes) 
  - [Sybil Resistance](#sybil-resistance)
    - [Pending Improvements](#pending-improvements)
  - [Mathematical Analysis](#mathematical-analysis)
  - [Using TCP](#using-tcp)
  - [Implementation Status](#implementation-status)
  - [Choice of Ciphersuite](#choice-of-ciphersuite)
  - [Modifying the Protocol](#modifying-the-protocol)
- [Contact Info](#contact-info)
- [Further Reading](#further-reading)


# Specification

Release date: 4/20/2018

Revision date: 10/8/2018

Revision number: 2


## Brief Summary

The Theseus DHT protocol runs over TCP. All traffic is encrypted. The core of the protocol is a set of RPCs exchanged over a protocol called KRPC (which is also used in the Mainline DHT implementation of Kademlia).

Peers possess a set of 20-byte, pseudorandom "node IDs". Peers keep routing tables which are maintained as in Kademlia; these track peers whose node IDs are close to any local node IDs by the XOR metric. Routing queries are supported via RPC. A peer may have as many node IDs as they like, though they'll have to track data stored at any of them.

Node IDs are generated by running a timestamp and a random bytestring through a state-of-the-art memory-hard cryptographic hash function, Argon2id. The result is trimmed and used. The node ID is always distributed along with its preimage, so that remote peers may verify that the two match. The timestamp is used to enforce an expiration date on node IDs. These measures [form the core of the network's Sybil resistance](#sybil-resistance).

Data is stored at addresses chosen from the same 160-bit space as node IDs. Any raw binary data may be submitted. ['Tags'](#data-tags) certifying some property about this data may be requested. Data is stored by sending it in an RPC message. Typically data is stored at the `k` closest peers to an address, where `k` is as in the Kademlia routing table. The value returned from this RPC will be an estimate of how long that data will be stored at the remote host. Note that it is not necessary for every one of these hosts to be honest: all we need is for one of them to be.

The storage duration for data depends on [many factors](#storage-durations).

_All_ protocol traffic is [indistinguishable from random noise](#encryption). Length-prefixing schemes are used on both protocol ciphertexts and plaintexts, and messages may be padded to any degree. This allows arbitrary message chunking, which is essential for [traffic obfuscation](#traffic-obfuscation).


## KRPC Format

From [BEP-5](http://www.bittorrent.org/beps/bep_0005.html):

> The KRPC protocol is a simple RPC mechanism consisting of bencoded dictionaries sent over UDP. A single query packet is sent out and a single packet is sent in response. There is no retry. There are three message types: query, response, and error.

> A KRPC message is a single dictionary with three keys common to every message and additional keys depending on the type of message. Every message has a key "t" with a string value representing a transaction ID. This transaction ID is generated by the querying node and is echoed in the response, so responses may be correlated with multiple queries to the same node. The transaction ID should be encoded as a short string of binary numbers, typically 2 characters are enough as they cover 2^16 outstanding queries. Every message also has a key "y" with a single character value describing the type of message. The value of the "y" key is one of "q" for query, "r" for response, or "e" for error.

> Queries, or KRPC message dictionaries with a "y" value of "q", contain two additional keys; "q" and "a". Key "q" has a string value containing the method name of the query. Key "a" has a dictionary value containing named arguments to the query.

> Responses, or KRPC message dictionaries with a "y" value of "r", contain one additional key "r". The value of "r" is a dictionary containing named return values. Response messages are sent upon successful completion of a query.

> Errors, or KRPC message dictionaries with a "y" value of "e", contain one additional key "e". The value of "e" is a list. The first element is an integer representing the error code. The second element is a string containing the error message. Errors are sent when a query cannot be fulfilled.

We [define a number of errors below](#errors). We specify six KRPC queries: `find`, `get`, `put`, `info`, `hs_suggest`, and `hs_request`. Applications based on Theseus may add their own queries in addition to these.


## RPCs


### find

This mirrors Kademlia's `find_node` query. Takes a target DHT address as an argument. The queried node returns the closest nodes to that target in its routing table. The precise number of contacts may depend on the state of the queried peer's routing table, but under ideal circumstances it should equal the routing table's value of K.

Arguments: `{"addr": <20-byte address>}`

Response: `{"nodes": <compact node info>}`


### get

Try to retrieve data from a node. Takes a DHT address as an argument. If the queried peer has no data to return, it instead offers routing info using the same return signature as `find_node`. If the address is omitted, all `addr: data` pairs stored at the node should be returned.

The `tags` optional argument, if provided, should map to a list of strings. Data without the specified tags listed will not be returned. If `tags` is omitted or left empty, then only untagged data will be returned.

The response format for untagged data is simply a list of data items, encoded as bytestrings.

For tagged data, it's a list of (n+1)-tuples, where n is the number of tags requested. Tag values are returned alphabetized by tag name.

Arguments: `{"addr": <20-byte address>, "tags": ["tag1", "tag2", ...]}`

Response:

`<datum>` denotes `[<bytes>, <tag>, <tag>, ...]` if tags were requested, `<bytes>` otherwise.

- `addr` given: `{"data": {<20-byte address>: [<datum>, <datum>, ...], ...}}`
- `addr` omitted: `{"data": [<datum>, <datum>, ...]}`
- No data at address: `{"nodes": [<compact node info>, ...]}`


### put

Store some data in the DHT. Takes an address as an argument. There are several optional arguments. The response should specify the amount of time, in seconds, for which the remote peer intends to store this data.

The `sybil` optional argument, if included, should map to 0 or 1 depending on whether the querying peer believes a Sybil attack targeting this address is taking place. This is essentially a hint to the queried peer that they should attempt to verify this claim and [take appropriate action](#sybil-resistance).

The `tags` optional argument should map to a list of desired tags for the submitted data. Only [a couple tags are currently supported](#data-tags). If unsupported tags are requested, the query should not fail: instead, the queried peer should just populate the corresponding value fields with empty bytestrings.

The `t` optional argument allows the querier to request a storage duration for their data. This may or may not be honored, at the query recipient's discretion. The recommended behavior is to set data storage durations as the minimum of this key's value (if given) and some internally-computed default duration.


Arguments: `{"addr": "<20-byte address>", "data": <bytes>, "tags": ["tag1", "tag2"], "sybil": <bool>}`

Response: `{"t": 99999}`


### info

Used for metadata exchange between peers. Both arguments are technically optional. If neither is provided, the query should be treated as a no-op and the response should be an empty dictionary.

The `info` optional argument allows the querier to advertise local info keys. This is primarily useful at the start of a connection or when a peer wants to announce a change in local info.

The `keys` optional argument, if included, should be a list of info keys the querying peer wants to request from the remote peer.

If `keys` is provided, the return value should include an `info` key which follows the same format as the `info` query argument.

Applications using the Theseus DHT should also feel free to add their own metadata keys, and are encouraged to use a uniform and distinctive prefix for these keys to avoid naming conflicts. For instance, Theseus-specific parameters like Bloom filters for search will be prefixed `theseus_`.

Arguments: `{"info": {"key1": <data>, "key2": <data>, ...}, "keys": ["key3", "key4", ...]}`

Response: `{"info": {"key3": <data>, "key4": <data>, ...}}`


### hs_suggest

Messages of this type are purely informational and may be exchanged any number of times between handshakes. Their purpose is to communicate re-handshake parameters that the sending party would find acceptable.

The following parameters need to be established:

The `initiator` argument should map to 1 if the querier wishes to play the role of initiator in the new handshake, and 0 if they wish to be the responder.

The `handshake` argument specifies the full Noise protocol name for the new handshake to be performed. Rules for handshake parameters are outlined in [the section on encryption](#encryption).

If the Noise handshake pattern is `KNpsk0` or `KKpsk0`, then the `initiator_s` argument should be present and should map to a static public key to be used by the initiator.

If the Noise handshake pattern is `NKpsk0` or `KKpsk0`, then the `responder_s` argument should be present and should map to a static public key to be used by the responder.

Arguments: `{"initiator": 1, "handshake": "Noise_KK_25519_ChaChaPoly_BLAKE2b", "initiator_s": "<32-byte Curve25519 public key>", "responder_s": "<32-byte Curve25519 public key>"}`

Response: `{}`


### hs_request

Messages of this type specify concrete re-handshake parameters. If the remote peer finds these parameters unacceptable, it may reply with an error code. A non-error response indicates that the remote node accepts the re-handshake parameters.

After sending a non-error response, the responder should immediately enter the new handshake. Likewise for the receiver, who should immediately enter the handshake after receiving such a response.

The arguments `initiator`, `handshake`, `initiator_s`, and `responder_s` are all specified as in `hs_suggest`.

The argument `psk` should be included in both the query and response. In each case it should map to a bytestring of arbitrary contents. It is strongly suggested that these contents be a random string of length equal to the output size of the hash function specified in the `handshake` argument.

The values of both the query and response's `psk` arguments are to be hashed using the `handshake` argument's specified hash function. Their hashes are then to be XORed and the resulting value used as a PSK for the new handshake (applied via the psk0 Noise protocol modifier).

Arguments: `{"initiator": 1, "handshake": "Noise_KK_25519_ChaChaPoly_BLAKE2b", "initiator_s": "<32-byte Curve25519 public key>", "responder_s": "<32-byte Curve25519 public key>", "psk": "<bytestring>"}`

Response: `{"psk": "<bytestring>"}`


## Errors

Errors at the KRPC level are prefixed 1xx. Errors at the Theseus DHT protocol level are prefixed 2xx. Errors of any other type are prefixed 3xx.

So far, the following error codes are defined:

- `1xx` level:
  - `100: Generic KRPC error`
  - `101: Invalid KRPC message`
  - `102: Internal error (KRPC)`
  - `103: Method not recognized`
- `2xx` level:
  - `200: Generic DHT protocol error`
  - `201: Invalid DHT protocol message`
  - `202: Internal error (DHT)`
  - `203: Tag not recognized`
- `3xx` level:
  - `300: Generic error`
  - `301: Rate-limiting active`


## Data Formats

- `<20-byte address>`: A bytestring containing a DHT address in network byte order.
- `<bytes>`: A bencoded bytestring.
- `<tag>`: Same as `<bytes>`.
- `<contact info>`: Info about a node and the peer providing it, as a bytestring. Formed by concatenating the following:
  - Node ID (20 bytes)
  - ID preimage (10 bytes)
  - IP address (4 bytes)
  - Port (2 bytes)
  - Curve25519 public 'node key' (32 bytes)
- `<compact node info>`: A bytestring containing the concatenation of any number of `<contact info>` entities.
- `<data>`: Arbitrary native bencoded data structure.
- `<bool>`: 0 or 1.
- `<32-byte Curve25519 public key>`: As returned by [`cryptography.hazmat.primitives.asymmetric.x25519.X25519PublicKey.public\_bytes()`](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/x25519/#cryptography.hazmat.primitives.asymmetric.x25519.X25519PublicKey).


## Required Keys

Peers must provide at least the following info keys:

* `peer_key`: A Curve25519 public key used as a static key when responding to incoming Noise connections.
* `ids`: A list of node IDs, with preimages.

An `extensions` info key is suggested for DHT-integrated applications that want to advertise extra functionality to their peers. This key should map to a list of short bytestrings enumerating the extensions in use. The namespace for extension names is of course shared between all applications on the DHT, so anyone making use of this feature are strongly encouraged to names that are not likely to give rise to collisions. For instance, when Theseus proper is built upon the Theseus DHT, its peers will advertise `"extensions": ["theseus"]`. Since the namespace for query names is also shared, it is encouraged, wherever reasonable, to prefix query names with a uniform extension name.


## Routing

A modified Kademlia-style routing table is used. This consists of "buckets" covering ranges whose union is the full address space, from 0 to 2<sup>160</sup>. Each bucket may contain up to `k` nodes.

When a new contact is discovered and inserted into the table, the bucket its ID falls into is identified. If this bucket has room, the node is inserted into the table. Otherwise, if one of the local peer's own node IDs falls into the bucket range, then the bucket is split. This replaces it with two new, smaller buckets which bisect the original bucket's range. The old bucket's contacts are moved into the new buckets, and then the insert is reattempted.

The Kademlia paper suggests implementing this structure as a binary tree.

We'll provisionally set `k=16` for now, pending full mathematical analysis. Peers are free to use higher values of k locally if they so desire.

Routing queries should return up to `k` of the closest 


## Address Selection


The proper operation of the DHT relies on addresses being uniformly distributed and nodes being unable to choose their own addresses. To achieve this, we allow nodes to choose their *ID preimage*, and derive their actual node IDs from a cryptographic hash of this preimage. The node ID and ID preimage must always be transmitted together so remote peers can verify that they match.

The hash function used is Argon2id. This is a state-of-the-art memory-hard hash function usually used for hashing passwords. It is designed to make parallelized brute-force search of the input space as difficult as possible. The work parameters we will use are memlimit=2<sup>28</sup> and opslimit=3 (these are the values of the PyNaCl library constants MEMLIMIT\_MODERATE and OPSLIMIT\_MODERATE, respectively).

The preimage format is UNIX time in network byte order followed by 6 bytes from a CSPRNG.

The rationale behind this design is discussed [here](https://wootfish.github.io/sohliloquies/2017/02/26/resisting-sybil-attacks-in-distributed_25.html).


## Data Tags

Tags are specified via a `tags` argument within individual RPCs. Nodes should implement all specified tags. If a node receives a request to populate tags it doesn't recognize, the node should respond with error 203 [as specified below](#errors).

The only specified tags at this time are `ip` and `port`. They should be populated with the observed IP or observed port of a remote peer. Remember that if NAT is in use, it may cause these fields to take unexpected values.


## Storage Durations

This is mostly left up to individual nodes to determine. In general, a node should try to hold on to any data it receives for as long as it can. Nodes should also try to report their intended storage durations as accurately as possible, ideally to within the second. It would make sense to implement a scheme where a node has a hard memory cap and it dynamically reduces storage times based on how close the node is to hitting this cap. A more detailed discussion of this topic is forthcoming.


## Encryption


### High-Level Overview

Encryption of Theseus protocol messages is handled through the Noise Protocol Framework. The authoritative documentation for Noise can be found [here](https://noiseprotocol.org/noise.html), and the Python library we use is [here](https://github.com/plizonczyk/noiseprotocol).

All traffic is encrypted, and all encrypted messages are indistinguishable from random noise. Messages may be chunked to arbitrary sizes, and plaintexts may optionally be padded before encryption, further reducing fingerprintability.


### Initial Handshake

In order to avoid any fingerprintable protocol preamble, we will specify a default handshake pattern and ciphersuite: `Noise_NK_25519_ChaChaPoly_BLAKE2b`. The `NK` pattern here provides for an exchange of ephemeral public keys to establish an encrypted channel, and for authentication of the responder (using their node key). The initial ephemeral key must be encoded with [Elligator](https://elligator.cr.yp.to/) to keep it from being trivially fingerprintable.


### Subsequent Handshakes

After the initial handshake and establishment of the encrypted channel, additional handshakes may be performed. These are negotiated through RPC queries and responses. Once the peers agree on parameters like the handshake pattern and the public keys to be used for authentication, they may discard their current `CipherState` objects and, within the same TCP connection, start from scratch executing a new handshake. In order for the new handshake's session to inherit the security properties of the old session, a PSK must be negotiated within the old session and included in the new handshake via the `psk0` modifier.

The handshake patterns which may be used are `NNpsk0`, `KNpsk0`, `NKpsk0`, `KKpsk0`.

The pattern may use any supported curve, cipher, or hash function. Wherever possible, the default choices of `Curve25519`, `ChaChaPoly`, and `BLAKE2b` should be favored. These defaults may change, though this will probably only happen if cryptographic weaknesses in any of them are discovered.

If for some reason two peers don't want to use a PSK, i.e. if they want to restart their Noise session from scratch, then rather than re-hanshaking they should just close and re-open their connection.


### Message Sizes

Every encrypted Theseus protocol message is preceded by an encrypted declaration of the protocol message's size. Whenever a plaintext is ready to send, the plaintext bytestring's length is calculated, encoded as a big-endian 32-bit integer, and encrypted, yielding a 20-byte ciphertext (4 message bytes + 16 AE tag bytes). This encrypted length announcement is sent, then the plaintext is encrypted and sent.

The process for receiving higher-level protocol messages is therefore essentially this:

1. Read bytes off the wire until we've received 20 bytes total.
2. Decrypt these 20 bytes of ciphertext and treat the resulting 4-byte plaintext as an unsigned, big-endian 32-bit integer N.
3. Read bytes off the wire until we've received N + 16 more bytes total.
4. Decrypt these N + 16 bytes. The resulting N plaintext bytes are the protocol message.
5. Repeat.

This scheme allows the size of every ciphertext to be known in advance, which in turn allows arbitrary message chunking without risk of any ambiguity around message boundaries. Individual packets sent across the wire can therefore be arbitrarily sized, meaning the protocol can assume essentially any traffic pattern.

It's probably worth noting that this scheme creates a theoretical limit on the size of Theseus protocol messages: 2<sup>32</sup> - 1 = 4,294,967,295 bytes. That's 4 GiB, so any application running up against this limit has probably made some big mistakes along the way, to the point where the size limit is the least of their concerns.

In environments which aren't likely to have 4 GiB of RAM to spare at any given moment, applications are encouraged to set smaller internal limits on message size -- maybe 2<sup>20</sup> bytes or so. This suggestion, while much smaller, is still conservatively large as a sort of future-proofing. Theseus DHT protocol traffic will probably never even come close to this limit. Individual Noise protocol messages are capped at 65535=2<sup>16</sup>-1 bytes of ciphertext, so protocol messages exceeding 65535 - 16 = 65519 bytes of plaintext will of course need to be sent in chunks.

It goes without saying that in cases where performance is critical, message chunking will only slow down the transfer of data between two peers, increasing the time required to perform tasks like lookups or information retrieval. Thus this feature is likely only of interest to the extremely privacy-conscious. In some ways (though notably _not_ where anonymity is concerned) the trade-off resembles that made by a person who decides to route all their web traffic through Tor. The critical thing here is that even if most users choose not to make this trade-off, _they still get to make the choice_. In stark contrast with most modern systems, here the decision of how far a user wants to go to protect their privacy is theirs to make.


### Plaintext Format

Each message contains an RPC embedded in a netstring. Anything after the end of the netstring is discarded. Thus any message may contain an arbitrary amount of padding, or no padding at all. Empty plaintexts with nothing but padding should be silently discarded and should not be considered errors.


# Brief Discussion

Release date: 4/20/2018

Revision date: 5/15/2018

Revision number: 1


## Peers and Nodes

Just to clarify: Users on the DHT run an individual peer. This peer has a routing table and a number of node IDs. Each node ID represents a specific node being hosted by the peer. When a peer's contact info is returned in a routing query, only the peer's closest node's ID is included.


## Sybil Resistance

Carrying out a Sybil attack aimed at censoring or modifying data at a specific key requires the ability to deploy at least `k` nodes near a target address. This requires finding hash preimages for at least `k` node IDs which all share a given prefix. The best known strategy for finding these nodes given a strong hash function is brute-force search, which Argon2id is specifically designed to render extremely computationally expensive.

Putting expiration dates on node IDs prevents malicious peers from squatting indefinitely on significant node IDs once appropriate preimages for them are found.

Brute-force search can also be used to just deploy a tremendous number of nodes across the entire network, if the attacker just uses every hash they generate. These node IDs are guaranteed to be evenly distributed across the address space, allowing us to mathematically estimate the impact of an adversary based on how fast they can produce new node IDs.

[Real-World Sybil Attacks in BitTorrent Mainline DHT](https://www.cl.cam.ac.uk/~lw525/publications/security.pdf) offers a taxonomy in which the targeted attack described above is termed a "vertical Sybil attack" and the broader, generalized attack is termed a "horizontal Sybil attack".

The size of the entire DHT peer network can be straightforwardly estimated. Prior research on this subject can be found here: [Measuring Large-Scale Distributed Systems: Case of BitTorrent Mainline DHT](https://www.cs.helsinki.fi/u/lxwang/publications/P2P2013_13.pdf). An accurate estimate of network size opens the door to all sorts of interesting [mathematical analysis](#mathematical-analysis) on network properties.

Carrying out a horizontal Sybil attack requires a huge increase in the number of nodes in the network. Carrying out a vertical Sybil attack requires a huge increase in the node density at a specific address. Both of these produce easily-identified signatures which allow the network to identify and take steps to mitigate in-progress Sybil attacks.

Reasonable countermeasures against Sybil attacks would include increasing storage duration for all data, increasing the storage radius for data (e.g. dynamically scaling from storing data at the `k` closest nodes to an address to the `2k` closest nodes.


## IPv6

Currently all traffic takes place over IPv4. This is just because it makes my life simpler as a developer -- for now. But there is a good reason to want IPv6 support: Most routers perform NAT on IPv4 traffic, whereas performing NAT on IPv6 is less common (which makes sense, since IPv4's dependence on NAT is one of the problems IPv6 was designed to solve). This general lack of NAT means that IPv6 is much more attractive in a peer-to-peer context, since it allows hosts positioned behind routers (as virtually all personal computers are) to communicate without the need for complications like hole-punching. Thus IPv6 support is a major priority, albeit a deferred one (for now).


### Pending Improvements

Presently it is possible for attackers to "steal" observed IDs. It is not hard to imagine a situation where an attacker with significant network presence could listen for IDs close to an address it wants to attack, then start announcing the observed node ID as its own. The peers closest to the address should have already seen an advertisement from the peer who originally generated the ID, and should thus reject the attacker's advertisement of the same ID (and in fact should probably blacklist the attacking peer). However, peers further away from the address could end up attributing this node ID to the attacker if they 1) have room in the relevant routing table bucket and 2) haven't already seen the node ID.

This could result in routing lookups which pass through the further peers leading to the attacker. It is difficult to model precisely how serious of a problem this is, but it should be mitigated nevertheless. It is perhaps worth noting that the attack is trivial to detect (as a lookup would almost certainly end up seeing the stolen ID attributed to both sets of contact info) but that detecting the attacker is much more difficult. Thus detecting the attack is not sufficient to curb its effectiveness.

This problem has a solution, which is simple in principle but challenging to design properly. The core idea is to include a peer's contact info in the calculation of their node IDs. This idea somewhat resembles a drafted extension to Kademlia: [BEP-42](http://bittorrent.org/beps/bep_0042.html).

I see at least four difficulties with this solution in our case.

First: I want to leave the door open to running Theseus peers as Tor onion services. Doing so properly is a nuanced problem. My goal here is to avoid adopting a solution exclusively geared towards peers who know and are comfortable disclosing their public IP. Such a solution would complicate the process of adding support for peers who have more extreme threat models. This is the main reason I'm describing a draft version of this solution here, rather than codifying it in the spec.

Second: I also want to leave the door open to IPv6. The reasons for this are discussed [above](#ipv6). The difficulties posed by making this scheme compatible with IPv6 addresses resemble those to do with supporting Tor onion services.

Third: These different identifiers -- IPv4 address, IPv6 address, Tor onion service descriptors -- contain differing amounts of entropy. My early writings on Sybil attack prevention discussed the idea of limiting node ID entropy as a way of bounding the worst-case impact of a Sybil attack. Lately I've soured on this idea somewhat, since if we're dynamically detecting and compensating for Sybil attacks then we probably don't need that bound after all and in fact we probably care more about address uniqueness than anything else. All the same, it is important from a theory perspective to carefully consider and account for the implications here regarding ID entropy.

Fourth: If we limit ourselves to the IPv4 case momentarily, we still have the problem that peers might not know their public IPs. This would for instance commonly be the case for anyone initiating a connecting from behind NAT. The solution is to allow peers to discover their own IP as reported by remote peers. The most straightforward and elegant way I see of adding this would be to do the following:

- Add a `tags` key to `put` responses, keying a dictionary which maps tag names to the values assigned for them. This key would only be required if the `put` request also had a `tags` key. This would allow the querying peer to see what values the remote peer associates with the given tags.
- Add an optional 'duration' key (or perhaps some smaller name, like 'ttl') to `put` queries. This would specify a desired storage duration for the data the query is requesting storage of. The remote peer would store the data for whichever is smaller between their default storage duration and the requested duration. Crucially, requesting a storage time of 0 would prevent data from being stored in the first place, but would still cause the remote peer to return a `tags` key if the original query had one.

We could also add a dedicated RPC, but that seems like an uglier solution to me. Both these modifications strike me as reasonable features to have regardless. It just so happens that together they also provide a mechanism for users to discover their own IPs without polluting the network or introducing new queries.

This subject will be addressed further after I have explored the topics of Tor integration and IPv6 support more thoroughly.


## Mathematical Analysis

`TODO: Lay out in-depth mathematical analysis based on points outlined above. (I have lots of analog notes on this. A detailed write-up is forthcoming.)`


## Using TCP

The choice to use TCP rather than UDP is a significant one and is not taken lightly. The essential motivation is that it simplifies the cryptography. For an idea of why, see [here](https://noiseprotocol.org/noise.html#out-of-order-transport-messages). Note in particular that including plaintext nonce values with messages would break our requirement that *all* protocol traffic be indistinguishable from random noise. Persistent connections also provide a convenient abstraction within which to perform multiple consecutive handshakes.

One complication: A TCP connection to a specific port will originate from an arbitrary 'ephemeral' port on the part of the connector. UDP can operate this way but doesn't have to, because it's connectionless. Thus protocols like Kademlia which operate over UDP can and do use their packets' source port to advertise the port they're listening for messages on -- a trick we can't use if our connections have to originate from ephemeral ports. Compensating for this requires provisions at the protocol level for communicating the port we're listening for connections on. This is why `listen_port` is a required datum in the `info` query.

A big issue here that we'll want to spend some time looking hard at once the reference implementation is otherwise mature and stable: NAT traversal. We may be able to work out a scheme for reachable nodes to perform some sort of hole punching to help NATed hosts to reach each other.

If hole punching doesn't pan out, another interesting possibility (which was touched on briefly in some of the Theseus blog posts back on Sohliloquies) would be to see if the network can support an onion routing overlay, and if so, whether it'd be viable for NATed hosts to make themselves available as "hidden services" served from other, publicly accessible hosts. This would also have other benefits for users willing or needing to trade performance for privacy -- but that's a story for another day.


## Implementation Status

The Twisted implementation is coming along well but is not yet complete. Some outstanding TODOs (see also [TODO.md](/todo.md):

- The NoiseWrapper protocol wrapper works, but implementing `hs_request` will require extending its functionality somewhat.
- Speaking of Noise, traffic obfuscation during the Noise handshake is not nearly as strong as once the handshake is complete. Still working on a fix for this.
- We also need to set up intermittent automatic routing lookups to keep the local routing table fresh.
- We do not yet have Elligator support. We'll either need to get this added into the Noise library or else shim it in at the protocol level.
- We have some unit tests, but the code coverage stats have a lot of room to improve.

Proposed Roadmap (subject to change):

1. ~~Finish writing up mathematical analysis of network dynamics and Sybil thresholds.~~ (formal analysis complete, writeup pending)
2. ~~Add ID check logic for node IDs received from remote peers.~~
3. ~~Add logic for inserting remote node IDs into the local routing table (tho maybe only after their ID checks pass)~~
  - One thing to be mindful of here: If we wait for ID checks to succeed before inserting into the routing table, this leaves a decently sized window where multiple peers could try to claim the same node ID.
  - In situations like this, it is _critical_ that precedence goes to whoever claimed the ID first.
  - The reasons why will be discussed in the formal analysis of the network.
4. ~~Implement `find` RPC.~~
5. ~~At this point the routing functionality will be complete! Seems like a good time to make a big push on writing unit tests.~~
6. ~~Implement node lookup logic.~~
7. Implement data store.
  - At this point, full end-to-end demos of DHT storage and retrieval (under non-adversarial conditions) are possible.
8. Implement network size estimation.
9. Add 'paranoid/non-paranoid' option to lookup logic, and have non-paranoid lookups automatically become paranoid if they detect anomalous peer density at the target address.
10. Implement Sybil attack. Run live attacks on a test peer swarm, and collect data on how effective the defenses are. Validate that the data agrees with the results obtained from formalisms and simulations.
11. Triage and implement other outstanding functionality like custom message sizing, handshake renegotiation, and Elligator support.

Some good starting points for anyone interested in helping out:

- If you're into cryptography, maybe look into what it would take to get Elligator support. It might make sense for this to end up being a pull request to the Noise library we use, rather than something that gets taken care of in the Noise wrapper here.
- Hacking AddrLookups into a network size estimation tool would be a fun project. Bit more of a research angle on this one, since there have been a few differing methodologies proposed.
- More unit tests are always needed. Code coverage hasn't been over 90% in ages and it'd be good to get it back up.
  - In particular, end-to-end tests of peer interactions through mocked network interfaces would be _super_ valuable.


## Choice of Ciphersuite

The default algorithm choices specified above were selected to provide as conservative and robust of a default configuration as possible. The only arguable exception is Curve25519, which, while still a fairly conservative choice, is still less so than Curve448. The deciding factor in this case was that the crypto libraries we're using provide good implementations of Curve25519, whereas Curve448 support comes from some native Python which is pretty much guaranteed not to be as well hardened against say side-channel or timing attacks. I'm totally willing to revisit this if we can get nice Curve448 bindings, maybe via OpenSSL or something.

Argon2id was chosen over my earlier favored algorithm, bcrypt, due to its state-of-the-art design and memory-hardness. Bcrypt is a great piece of work which has stood the test of time exceptionally well, but by nature of being CPU-hard rather than memory-hard it is less costly to mount massively parallel attacks on bcrypt using e.g. FPGAs. The memory overhead required for background verification of Argon2id hashes on a user's machine is also likely to be less impactful on performance than the CPU overhead required to verify bcrypt hashes of comparable hardness.

BLAKE2b is favored over SHA512 because it is faster, based on a more modern and robust construction (no length-extension attacks!), and doesn't suffer from any ominous reduced-round preimage resistance breaks like the SHA-2 family has. SHA512 still seems secure enough for the time being, of course, but if I had to bet on which algorithm I think'll be looking better 5 or 10 years from now, I'd bet on BLAKE2b.


## Modifying the Protocol

For now, let's just use GitHub issues for discussing potential protocol modifications. We'll probably want to come up with something better down the road, but we can worry about that then.

If you want to develop a protocol extension that doesn't impact core functionality, you don't need any sign-off from me or anyone to do that. Still, I'd like to hear from you! Drop me a line.


# Contact Info

If you want to get in touch with me (Eli), you can reach me a couple different ways:
- [Twitter](#https://twitter.com/elisohl): my DMs are open.
- Email: my first and last name, with no punctuation, at gmail.
- Signal: Send a Twitter DM or email asking for my personal number. Sorry, but I don't have a dedicated phone number to share publicly.
- Github: I try to keep a close eye on this repo, so opening an issue or pull request would also work to get my attention.

All else being equal, reaching out over Twitter DMs or here on Github are probably the most reliable ways of reaching me.


# Further Reading

The blog posts listed here are not necessarily up to date, but they reflect my thinking on these topics across the last couple years, and may be helpful to people looking for additional information or context for any of the ideas discussed above.

This is only a small selection of blog posts I've written on aspects of Theseus's design. If you're interested, most of the other posts can be found in links at the tops of the ones listed here.

On encryption:
- [Resisting Man-in-the-Middle Attacks in P2P Networks](https://wootfish.github.io/sohliloquies/2017/06/11/transient-public-keys-for-resisting.html)
- [Message Encryption in Theseus](https://wootfish.github.io/sohliloquies/2017/06/10/message-encryption-in-theseus.html)

On Sybil attacks:
- [Resisting Sybil Attacks in Distributed Hash Tables](https://wootfish.github.io/sohliloquies/2017/02/26/resisting-sybil-attacks-in-distributed_25.html)

For posterity, the (obsolete!) version 0.1 protocol spec:
- [Theseus Protocol v0.1 Overview](https://wootfish.github.io/sohliloquies/2017/04/21/theseus-protocol-v01-overview.html)
