# Theseus DHT Protocol

Theseus DHT is a distributed hash table with unusually strong security properties.

It is derived in large part from Kademlia, an efficient algorithm which is good at handling benign failures but bad at handling malicious interference. In particular, Kademlia is very vulnerable to Sybil attacks, which can result in the modification or erasure of arbitrary data in the network.

The Theseus DHT protocol addresses these and other concerns, mitigating Sybil attacks through a combination of several novel strategies. It also adds features like strong encryption, optional authentication, optional perfect forward secrecy, and more. The network's Sybil resistance also increases as the network itself grows.

To a passive observer, all Theseus DHT protocol traffic is indistinguishable from random noise. Even message lengths can be made to follow arbitrary patterns or no pattern. All this makes the protocol very hard to fingerprint. Any node which is able to get a trusted introduction to the network also enjoys considerable protection against man-in-the-middle attacks. Standard, well-studied cryptographic primitives are used throughout, and the specific ciphersuites used are configurable.

Theseus DHT is being developed as a component of the overall Theseus project. However, the DHT's resilience to Sybil attacks increases as the network gets bigger. Any app which requires a DHT providing these security features may feel free to use Theseus DHT. Features for per-app namespacing are included, to prevent naming conflicts. The larger the network, the better and more secure it is for everyone.

## Table of Contents

- [Specification](#spec)
  - [Transport](#transport)
  - [Encryption](#encryption)
    - [Initial Handshake](#initial)
    - [Subsequent Handshakes](#subsequent)
    - [Declaring Message Sizes](#sizes)


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

#### Declaring Message Sizes

Theseus uses a netstring-like strategy of prepending an encrypted declaration of each ciphertext's length to each ciphertext before sending it. The length declarations are fixed to 32 bits, so their ciphertexts also have a fixed length: 4 bytes for the length field, followed by 16 bytes for the AE tag. This allows the size of every ciphertext to be known in advance. This is convenient for resisting traffic analysis, because it allows message chunking without risk of ambiguity regarding message boundaries.

The consequence of allowing this level of chunking is that the data payloads of individual packets sent across the wire can be arbitrarily sized and message delineation will still be utterly unambiguous. This is a nice property to have,


