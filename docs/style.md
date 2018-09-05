# Style Guide

## General Rules

PEP-8 style should be followed as much as possible.

Internal-only "helper" methods should be prefixed with an underscore, to hint
that they are non-public.


## Twisted Style

Twisted predates PEP-8, and some of Twisted's naming conventions differ from
PEP-8's. Neither can be expected to change.

Most notably, Twisted uses mixedCase names for callbacks:
`Protocol.connectionMade` or `Protocol.connectionLost`, for instance. PEP-8
would have these written as `Protocol.connection_made` or
`Protocol.connection_lost`, but of course code implementing Twisted interfaces
must follow their naming conventions.

One option is to discard PEP-8's method naming style in favor of Twisted's. The
advantage is internal consistency; the downside is external inconsistency. In
particular, this project is intended to be able to serve as a component of
larger applications, and following Twisted's naming conventions throughout
would put these applications in the same position where Twisted has put us.

This seems unacceptable, and so the verdict is that _Twisted callbacks will use
Twisted-style names, but all other methods will follow PEP-8._

This comes at something of an aesthetic cost, since some objects like
KRPCProtocol will be forced to mix the two method naming styles. However, this
is seen as the least-worst reconciliation. It also provides an easy way of
finding out at a glance whether or not a given method is part of a Twisted
interface.
