# Introduction

Honestly generated node addresses in Theseus DHT are evenly distributed throughout the address space.
As a result, they are amenable to analysis via straightforward statistical models.
These statistical models allow us to detect the presence of even sophisticated Sybil attacks on data in the network.


(TODO: figure out how to do nice eqn rendering)


# DHT attacks - overview

Let us first remind ourselves of the primary categories of attack on a Kademlia-based DHT.


## Horizontal Sybil attack

This attack is concerned with flooding the network with as many Sybil nodes as possible.
Goals of this attack include monitoring of network data and traffic, indiscriminate disruption of data storage, and gaining a foothold to enable disruption of the routing overlay.

Performing this attack in Theseus DHT requires computing the proof-of-work function many times.
Since this function's outputs are uniformly distributed, an attacker wishing to maximize their number of nodes deployed will deploy nodes uniformly throughout the address space.
Also, the maximum number of nodes an adversary is capable of deploying is bounded by the compute power available to them, which is a powerful property for threat modeling.
Mathematical analysis of the DHT suggests for significant disruption of storage to succeed, Sybil attackers would have to outnumber honest peers many-to-one (TODO exact figures).
Since the total number of nodes in the peer swarm is easily estimated, an explosion in size would be easily detected and would prompt aggressive investigation.


## Vertical Sybil attack

This attack is concerned with deploying a large number of peers close to a specific address.
The goal of this attack is to prevent reliable data storage at the target address. Undermining data storage at the address's close neighbors is possible as well.

Since no effective cryptanalysis of Theseus DHT's proof-of-work function, Argon2, is yet known, there is no known better way of finding these proximate addresses than exhaustive search.
Thus, the cost of a vertical Sybil attack is at least as great as that of a horizontal Sybil attack, and the only benefit of the vertical attack is relative stealth.

However, for a given redundancy factor `k`, a successful vertical Sybil attack would require deploying (at least) `k` Sybil nodes at addresses closer to the target address than the closest honest peer.
Since the number of honest peers can be estimated and the distribution of honest peers is uniform, the deviation this attack produces from expectation is trivially detected.
The precise methodology for this test is outlined in the next section.


## Eclipse attack

This attack is concerned with subverting the DHT's routing overlay.
The idea is that by having Sybil nodes only reply to routing queries with other Sybil nodes, routing queries are likely to converge exclusively to a set of Sybil nodes.
The result of this would be general inability of honest peers to find each other, giving the attacker total control over which peers and what data may be reached.

The original paper for S/Kademlia provides a good summary of this attack and of its probability of success.
There turn out to be surprisingly effective countermeasures, and the probability of their success in defending against the attack is easily modeled.
The only two data points that this model requires are population estimates for the number of honest and Sybil nodes in the network.

Note that as long as a decently accurate estimate of total network size can be obtained, this attack does not actually impact the statistical tests given here.
After all, when our goal in the first place is to detect whether our routing queries are exclusively reaching Sybil nodes, an attack focused on routing us to those exact nodes is not terribly frightening.

The only real concern here is with obtaining a reliable size estimate in the first place.
If a huge number of nodes deployed as part of a widespread horizontal Sybil attack are used to launch an eclipse attack, they could subvert the lookups used to make this initial size estimate, undermining everything that takes place past this point.
We have two defenses against this risk:
First, the model given in the S/Kademlia paper gives an optimized lookup algorithm which maximizes our chances of success, as well as a precise model of how likely this algorithm is to succeed;
Second, the statistical tests described below provide _extreme_ confidence (5 to 10 sigmas at minimum) in their results.
This leaves us plenty of room to compensate for a skewed initial size estimate: rather than having a test succeed at the 99.999...% confidence threshold we are theoretically afforded, we could have it succeed at a much looser threshold, e.g. 80% or 90%.


# Statistical analysis


## Preliminaries

In this section we will assume that an estimate of the number of uniformly distributed nodes in the network is available.
Denote this estimate by `n`.

_(Footnote: In most of my other writings on Theseus, `n` denotes the number of_ honest _peers, whereas here it denotes the number of peers not actively engaged in a vertical Sybil attack -- i.e. honest only from that perspective -- a subtle distinction but perhaps still one worth highlighting)_

Consider the distances of these `n` nodes from an arbitrary address. Since the `xor` distance metric is bijective, these distances are uniformly distributed in the same space as node addresses.

Let `L` denote the number of bits in a node address, so that for any distance `d`, `0 <= d < 2**L`.

Discrete analysis of the distribution of these distances is possible, but it is much more straightforward and computationally tractable to apply a continuous approximation.
For large L, this approximation is extremely close and reliable.

To this end, and for convenience, let `F(d) = (d+1) / 2**L`.

Running our distances through this function `F` lets us conceptualize them as (extremely close approximations of) continuous random variables on the range (0, 1).

Modeling the distribution of the `i`th-least of `n` ordered, independent, uniform, continuous random variables on (0, 1) is a common textbook problem in statistics.
The surprisingly simple answer is that these random variables all follow special cases of the beta distribution, specifically with shape parameters `k` and `n-i+1`.
The corresponding CDFs are thus easily expressed in terms of the regularized incomplete beta function (`scipy.special.betainc`).

`CDF_i(x) = scipy.special.betainc(i, n-i+1, F(x))`

In the special case of `i = 1`, this simplifies to: `CDF(x) = 1 - (1 - F(x))^n`. The expectation for this case is simply `1/(n+1)`.

The expectation in the general case is `i/(n+1)`.


## Detecting vertical Sybil attacks

Our null hypothesis is that no vertical Sybil attack is taking place at the target address.

As mentioned above, for a vertical Sybil attack to succeed, the attacker needs to deploy at least `k` Sybil nodes with smaller distances from the target address than the closest honest node.
The expected distance of the closest honest node is `1/(n+1)`.

Thus, if a vertical Sybil attack is underway, it would (on average) produce an observation of the `k`th-least node having a distance of less than `1/(n+1)`.

The probability of this happening under the null hypothesis is `CDF_k(1/(n+1))`. A table of this CDF's values for various `n`, `k` is below.

| n       | k  | CDF
| ------- | -- | ---------------------- |
| 100     | 4  | 0.017788222205228858   |
| 1000    | 4  | 0.018865795846458182   |
| 10000   | 4  | 0.0189758968849804     |
| 1000000 | 4  | 0.01898803423433115    |
| 100     | 8  | 7.652805269233713e-06  |
| 1000    | 8  | 9.960649955297324e-06  |
| 10000   | 8  | 1.0220034299933122e-05 |
| 1000000 | 8  | 1.0248904696647503e-05 |
| 100     | 16 | 5.233507484465067e-15  |
| 1000    | 16 | 1.6547015153199243e-14 |
| 10000   | 16 | 1.84538119221331e-14   |
| 1000000 | 16 | 1.8675384162042756e-14 |
| 100     | 32 | 5.398471826823071e-39  |
| 1000    | 32 | 8.728919078077626e-37  |
| 10000   | 32 | 1.3718289720941933e-36 |
| 1000000 | 32 | 1.4410188923275412e-36 |

For `k >= 8` the probability of the described event under the null hypothesis is astonishingly low.

Note also that the test's results are largely invariant with regard to network size.


## Estimating network size

Various methods for estimating the size of a Kademlia-like network have been given in the literature.

The typical method is to walk a certain subregion of the address space, count the number of nodes in it, then scale this up based on the size of the subregion to get an estimate for the whole network.
This method is not without flaws (TODO: cite paper on correction factors).
Even when correctly implemented, the problem of choosing a properly sized subregion remains.
The cited paper's authors' best contribution here is to just offer a range of sizes which worked for them in the context of measuring MLDHT.

On top of the difficulty of correctly implementing this algorithm, the algorithm's overhead is worrying.
It requires a large number of lookup queries in order to enumerate all nodes in a given region (for some sense of the overhead involved, the cited paper is very satisfied to report that their implementation can run in under 5 seconds).
As a consequence, expecting all peers to maintain network size estimates would introduce a _significant_ amount of baseline network traffic, and this baseline would grow at least linearly as the network grows and peer density increases.

Luckily, better options are available.
In particular, systems like Theseus DHT which take steps to enforce even distribution of node addresses may leverage more sophisticated statistical methods may leverage more sophisticated statistical methods.

It was established above that the distributions of the `k` closest nodes to a given address follow the beta distribution.
The specific distribution is parameterized in terms of the total number of nodes, and the rank of the given node (i.e. closest, second-closest, third-closest, etc).

This means we can straightforwardly derive the expected value for the distance of the `i`th node from any arbitrary address.
This expectation is defined in terms of `i` and `n` where, like above, `n` is total network size.
As mentioned above, the expectation for the properly parameterized beta distribution is simply: `k/(n+1)`.

By finding the closest nodes to a given address, taking their distances from the target address.
