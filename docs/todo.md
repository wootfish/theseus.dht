# TODO

* Sort out ContactInfo. my pipe dream is to make it somehow generalize to cover raw IP/port pairs but also Tor hidden services and other alternate channels; this might be easier said than done, though, and we'll have to tweak the spec to cover this as well.
* Clean up NoiseWrapper (more details in TODOs in that file) (probably first step is to just write out a rigorous state machine for it on paper and make sure the implementation matches that spec)
    * Traffic obfuscation is totally missing from there and the issue of how best to add it is an interesting design problem. Retaining total flexibility is harder than it sounds.
    * Implementing `hs_request` will also require extending the wrapper's functionality somewhat.
    * We also do not yet have Elligator support. We'll either need to get this added into the Noise library or else shim it in at the protocol level.
* Add configurable paranoia to the lookup system, with doubling-back on paths that reached dishonest nodes
* Follow up on TODOs in plugins.py
* Intermittent automatic routing lookups to keep the local routing table fresh would be good. Currently these are run at addr generation and at no other time.
* Expand unit test suite more
