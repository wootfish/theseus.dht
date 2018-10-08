# TODO

* Sort out ContactInfo. my pipe dream is to make it somehow generalize to cover raw IP/port pairs but also Tor hidden services and other alternate channels; this might be easier said than done, though, and we'll have to tweak the spec to cover this as well.
* Clean up NoiseWrapper (more details in TODOs in that file) (probably first step is to just write out a rigorous state machine for it on paper and make sure the implementation matches that spec)
    * Also have to figure out how to add message padding in here -- how do we want to make that configurable, even? Seems difficult to do right.
* Add configurable paranoia to the lookup system, with doubling-back on paths that reached dishonest nodes
* Follow up on TODOs in plugins.py
* Expand unit test suite more
