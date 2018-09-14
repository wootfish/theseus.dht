from twisted.internet.defer import Deferred
from twisted.logger import Logger
from twisted.protocols.basic import NetstringReceiver
from twisted.python.failure import Failure
from twisted.plugin import getPlugins

from .plugins import IKRPC
from .bencode import bencode, bdecode
from .errors import PluginError, BencodeError, TheseusProtocolError, errcodes
from .errors import KRPCError, Error100, Error101, Error102, Error103, Error300

from os import urandom


# TODO stare at KRPCProtocol & meditate on whether it can be streamlined


class KRPCProtocol(NetstringReceiver):
    log = Logger()
    max_name_size = 32
    _peer = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.query_handlers = {}
        self.response_handlers = {}

        self.open_queries = {}
        #self.deferred_responses = {}

        for provider in getPlugins(IKRPC):
            # TODO does raising an exception return control to the event loop?
            # if so, any plugins loaded after the first failing one would be
            # skipped, which would be a bug.
            if type(provider.name) is not bytes or len(provider.name > self.max_name_size):
                raise PluginError("Bad RPC name in plugin")
            if provider.name in self.query_handlers:
                raise PluginError("Multiple plugins tried to claim same RPC")

            # TODO log this plugin use

            self.query_handlers[provider.name] = provider.query_handler
            self.response_handlers[provider.name] = provider.response_handler

    def connectionMade(self):
        super().connectionMade()

        peer = self.transport.getPeer()
        self._peer = peer.host + ":" + str(peer.port)

    def connectionLost(self, reason):
        while self.open_queries:
            self.open_queries.popitem()[1].errback(reason)

    def stringReceived(self, string):
        try:
            krpc = bdecode(string)
            if type(krpc) is not dict:
                raise Exception
            txn_id = krpc.get(b't')
            msg_type = krpc.get(b'y')
            if msg_type not in (b'q', b'r', b'e'):
                raise Exception

        except Exception:
            # malformed message, and we don't have enough info for a proper
            # response, so... fuck it
            self.transport.loseConnection()
            KRPCProtocol.log.warn("{peer} - Received malformed message: {msg}", peer=self._peer, msg=string)
            return

        #if txn_id in self.deferred_responses:
        #    # reused existing txn_id -- errback that txn's existing query
        #    ...

        if msg_type == b'q':
            query_name = krpc.get(b'q')
            args = krpc.get(b'a')
            if None in (query_name, args) or type(args) is not dict:
                self._send_error(txn_id, Error101)
            else:
                self._handle_query(txn_id, query_name, args)

        elif msg_type == b'r':
            args = krpc.get(b'r')
            deferred = self.open_queries.pop(txn_id, None)

            if deferred is None or args is None:
                # probably best to give this node a healthy bit of distance
                self.transport.loseConnection()
                if deferred:
                    deferred.errback(Exception("Remote peer is broken"))
            else:
                KRPCProtocol.log.info("{peer} - Query response (txn {txn}): {args}", peer=self._peer, txn=txn_id.hex(), args=args)
                deferred.callback(args)

        elif msg_type == b'e':
            try:
                errcode, errinfo = krpc[b'e']
                if type(errcode) is not int or type(errinfo) is not bytes:
                    raise Exception
                errinfo = errinfo.decode("UTF-8")
            except Exception:
                errcode, errinfo = None, None

            KRPCProtocol.log.warn("{peer} - Received an error on txn {txn}. code: {code}, info: {info}",
                        peer=self._peer, txn=txn_id.hex(), code=errcode, info=errinfo)

            if txn_id in self.open_queries:
                KRPCProtocol.log.debug("{peer} - txn {txn} - Firing errback with {errtype}",
                        peer=self._peer, txn=txn_id.hex(), errtype=errcodes.get(errcode, TheseusProtocolError))
                self.open_queries.pop(txn_id).errback(
                        errcodes.get(errcode, TheseusProtocolError)(errinfo)
                        )
            else:
                KRPCProtocol.log.info("{peer} - Error received for unrecognized txn {txn}", peer=self._peer, txn=txn_id.hex())

    def _handle_query(self, txn_id, query_name, args):
        if query_name not in self.query_handlers:
            KRPCProtocol.log.debug("{peer} - Unsupported query {name} requested in {proto}", peer=self._peer, name=query_name, proto=self)
            self._send_error(txn_id, Error103)
            return

        try:
            # event callback for subclasses
            self.on_query(txn_id, query_name, args)
        except KRPCError as err:
            self._send_error(txn_id, err)
            KRPCProtocol.log.error("{peer} - Error in subclass's query event hook", peer=self._peer)
            return

        KRPCProtocol.log.debug("{peer} - Received query (txn {txn}): {query_name} {args}",
                       peer=self._peer, txn=txn_id.hex(), query_name=query_name, args=args)

        try:
            result = self.query_handlers[query_name](args)

            if type(result) is dict:
                #self.deferred_responses.pop(txn_id, None)
                try:
                    self._send_response(txn_id, result)
                except BencodeError:
                    KRPCProtocol.log.error("{peer} - Internal error trying to bencode the following response (txn {txn}): {result}",
                                   peer=self._peer, txn=txn_id, result=result)
                    raise Error102

            elif isinstance(result, Deferred):
                if not result.called:
                    KRPCProtocol.log.debug("{peer} - Deferring response to query (txn {txn_id})", peer=self._peer, txn_id=txn_id.hex())

                def callback(retval):
                    KRPCProtocol.log.debug("{peer} - Sending deferred response (txn {txn_id}) {retval}", peer=self._peer, txn_id=txn_id.hex(), retval=retval)
                    self._send_response(txn_id, retval)
                result.addCallback(callback)

            else:
                self.log.warn("{peer} - '{name}' query produced result of type {t}", peer=self._peer, name=query_name, t=type(result))
                raise Error100

        except KRPCError as err:
            KRPCProtocol.log.error("{peer} - Error {n} encountered", peer=self._peer, n=err.errcode)
            self._send_error(txn_id, err)

        except Exception:
            KRPCProtocol.log.warn("{peer} - Unexpected error responding to query {name} (txn {txn})",
                           peer=self._peer, name=query_name, txn=txn_id)
            KRPCProtocol.log.debug("{f}", f=Failure())
            self._send_error(txn_id, Error300)

    def on_query(self, txn_id, query_name, args):
        """
        To be overridden in subclasses wishing to hook the query event. Raise a
        TheseusProtocolError in this function to abort the query and send the
        same error code, along with any arguments passed to the
        TheseusProtocolError, to the remote node.
        """

    def _on_error(self, failure):
        """
        To be overridden in subclasses wishing to hook the error event.
        """
        return failure

    def send_query(self, query_name, args):
        if type(query_name) is str:
            query_name = query_name.encode("ascii")  # make sure type(query_name) is bytes

        txn_id = urandom(2)
        KRPCProtocol.log.info("{peer} - Sending query (txn {txn}): {query} {args}", peer=self._peer, txn=txn_id.hex(), query=query_name, args=args)
        self.sendString(bencode({b't': txn_id, b'y': b'q', b'q': query_name, b'a': args}))

        deferred = Deferred()
        if query_name in self.response_handlers:
            deferred.addCallback(self.response_handlers.get(query_name))
        deferred.addErrback(self._on_error)

        self.open_queries[txn_id] = deferred
        return deferred

    def _send_response(self, txn_id, retval):
        response = {b't': txn_id, b'y': b'r', b'r': retval}
        bencoded = bencode(response)
        KRPCProtocol.log.info("{peer} - Sending response: {response}", peer=self._peer, response=response)
        self.sendString(bencoded)

    def _send_error(self, txn_id, err):
        if isinstance(err, KRPCError):
            errtup = (err.errcode, ''.join(err.args) or err.errtext)
        elif type(err) is type and issubclass(err, KRPCError):
            errtup = (err.errcode, err.errtext)
        else:
            errtup = (Error300.errcode, Error300.errtext)
        KRPCProtocol.log.info("{peer} - Sending error (txn {txn}) {err}", peer=self._peer, txn=txn_id.hex(), err=errtup)
        self.sendString(bencode({b't': txn_id, b'y': b'e', b'e': errtup}))
