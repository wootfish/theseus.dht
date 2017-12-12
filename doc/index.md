# Theseus DHT Protocol

Theseus DHT is a distributed hash table with unusually strong security properties.

It is derived in large part from Kademlia, an efficient algorithm which is good at handling benign failures but bad at handling malicious interference. In particular, Kademlia is very vulnerable to Sybil attacks, which can result in the modification or erasure of arbitrary data in the network.

The Theseus DHT protocol addresses these and other concerns, mitigating Sybil attacks through a combination of several novel strategies. It also adds features like strong encryption, optional authentication, optional perfect forward secrecy, and more. The network's Sybil resistance also increases as the network itself grows.

To a passive observer, all Theseus DHT protocol traffic is indistinguishable from random noise. Even message lengths can be made to follow arbitrary patterns or no pattern. All this makes the protocol very hard to fingerprint. Any node which is able to get a trusted introduction to the network also enjoys considerable protection against man-in-the-middle attacks. Standard, well-studied cryptographic primitives are used throughout, and the specific ciphersuites used are configurable.

Theseus DHT is being developed as a component of the overall Theseus project. Since the DHT's resilience to Sybil attacks increases as the network gets bigger, this DHT component is being made separately available so that it may be integrated into any other app which needs a DHT providing these features. Support for per-app namespacing is included. The larger the network gets, the better and more secure it is for everyone.

## Table of Contents

- [Specification](#specification)
  - [Transport](#transport)
  - [Encryption](#encryption)
    - [Initial Handshake](#initial-handshake)
    - [Subsequent Handshakes](#subsequent-handshakes)
    - [Declaring Message Sizes](#declaring-message-sizes)


## Specification

### Transport

We deviate from Kademlia by using TCP rather than UDP at the transport layer. The move to a stateful, connection-based protocol adds some overhead but makes the cryptography much easier by providing reliability and ordered delivery.

### Encryption

#### Initial Handshake

Encryption is handled through the Noise Protocol Framework. This is what allows us to produce seemingly-random protocol traffic. The authoritative documentation for Noise can be found [here](https://noiseprotocol.org/noise.html), and the Python library we will use is [here](https://github.com/plizonczyk/noiseprotocol). In order to avoid any (fingerprintable) protocol preamble, we will specify a default handshake and ciphersuite: `Noise_NN_448_ChaChaPoly_SHA512`. The NN pattern here provides for an exchange of ephemeral public keys to establish an encrypted channel. The public keys should be Ellegator-encoded to keep them from being trivially fingerprintable.

    (TODO: make doubly sure using Elligator here is viable)

#### Subsequent Handshakes

After the initial handshake and establishment of the encrypted channel, additional handshakes may be performed. These are negotiated through RPC queries and responses. Once the peers agree on parameters like the handshake pattern and the public keys to be used for authentication, they may discard their current CipherState objects and, within the same TCP connection, start from scratch executing a new handshake. In order for the new handshake's session to inherit the security properties of the old session, a PSK must be negotiated within the old session and included in the new handshake via the psk0 modifier. Either or both parties may suggest a PSK. If multiple keys are chosen, the actual PSK used should be the XOR of the keys' SHA256 hashes.

The handshake patterns which may be used are `NNpsk0`, `KNpsk0`, `NKpsk0`, `KKpsk0`.

The pattern may use any supported curve, cipher, or hash function. Wherever possible the default choices of Curve448, ChaChaPoly, and SHA512 should be favored. These defaults may change if cryptographic weaknesses in any of the aforementioned primitives are discovered.

If for some reason two peers don't want to use a PSK, i.e. if they want to restart their Noise session from scratch, then rather than re-hanshaking they should just close and re-open their connection.

#### Message Sizes

Every encrypted Theseus protocol message is preceded by an encrypted declaration of the protocol message's size. Whenever a plaintext is ready to send, the plaintext bytestring's length is encoded as a big-endian 32-bit integer and encrypted, yielding a 20-byte ciphertext (4 message bytes + 16 AE bytes). This is sent, then the plaintext is encrypted and sent. This scheme allows the size of every ciphertext to be known in advance, which in turn allows arbitrary message chunking without risk of ambiguity regarding message boundaries. Thus, individual packets sent across the wire can be arbitrarily sized, and can thus mimic essentially any traffic pattern.

It's worth noting that this scheme creates a theoretical limit on the size of Theseus protocol messages: 2<sup>32</sup> - 1 = 4,294,967,295 bytes. That's 4 GiB, so any application running up against this limit has probably made some big mistakes along the way, to the point where the size limit is almost certainly the least of their concerns.

In environments which aren't likely to have 4 GiB of RAM to spare at any given moment, applications are encouraged to set smaller internal limits on message size -- maybe 2<sup>20</sup> bytes or so. This suggestion, while much smaller, is still conservatively large as a sort of future-proofing. Theseus traffic will probably never even come close to this limit, except perhaps when exchanging uncompressed Bloom filters, and even then messages should fall comfortably short of the max size. Individual Noise protocol messages are capped at 65535 bytes of ciphertext, so Theseus protocol messages which exceed 65535 - 16 = 65519 bytes of plaintext will of course need to be sent in parts.

#### Plaintext Format

To aid with traffic masking, any message may contain arbitrary amounts of padding (or no padding at all). Each message starts with the RPC encoded as a netstring. Anything after the end of the netstring is discarded. Padding must be included when calculating the length of the plaintext,


