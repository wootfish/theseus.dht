# TODO

* Write the data store. Roughly, it should have:
    * a `put` method for storing address : value pairs. Both of type bytes. This should store the data, then choose and return the timeout assigned to that data.
    * a `get` method with an optional address argument; if this is omitted, it should return everything stored.
    * This API is subject to change if something else turns out to make more sense in the implementation process. for instance, should we have `get` return a dict of lists of bytes unconditionally? or just return a list of bytes if addr is given, and dict if not? or decompose it into `get` and `get_all`, and give them different function signatures? deep questions
    * The timeout should depend on how much memory is in use vs the maximum memory allocated; the closer we are to full, the faster we time new stuff out, with the goal of never actually hitting full -- this may be easier said than done, we'll see
* Sort out ContactInfo. my pipe dream is to make it somehow generalize to cover both raw IP/port pairs and Tor hidden services; this might be easier said than done, though, and we'll have to tweak the spec to cover this as well.
* Revamp the hasher to clean it up (inlineCallbacks will help) and to support the new hash model that I've figured out (but have not yet properly written down)
* Clean up NoiseWrapper (more details in TODOs in that file) (probably first step is to just write out a rigorous state machine for it and make sure the implementation matches that spec)
    * Also have to figure out how to add message padding in here -- how do we want to make that configurable, even? Seems difficult to do right.
* Share constants like k and L better. Maybe put them in the config? Tho we don't want end users touching them...
* Implement lookup logic. This is gonna take a while.
* Follow up on TODOs in plugins.py
* Someday, rewrite the routing table to be less ugly. Preferably using a prefix tree.
* Expand unit test suite a lot
