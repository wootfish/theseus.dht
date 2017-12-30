from twisted.protocols.basic import NetstringReceiver
from twisted.internet.defer import Deferred
from twisted.logger import Logger

from .bencode import bencode, bdecode
from .errors import BencodeError, TheseusProtocolError, errcodes

import os
import traceback


class KRPCProtocol(NetstringReceiver):
    log = Logger()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.query_handlers = {}
        self.response_handlers = {}
        self.open_queries = {}
        self.deferred_responses = {}

    def connectionLost(self, reason):
        for txn_id, deferred in self.open_queries.items():
            deferred.errback(reason)

    def stringReceived(self, string):
        try:
            krpc = bdecode(string)
            assert type(krpc) is dict
            txn_id = krpc[b't']
            msg_type = krpc[b'y']
            assert msg_type in (b'q', b'r', b'e')
        except (BencodeError, KeyError, AssertionError) as e:
            # malformed message, and we don't have enough info for a proper
            # response, so... fuck it
            self.transport.loseConnection()
            self.log.info("Received malformed message: {msg} {err}", msg=string, err=e)
            return

        if msg_type == b'q':
            query_name, args = krpc.get(b'q'), krpc.get(b'a')
            if None in (query_name, args):
                self.sendError(txn_id, (203, "missing required argument"))
                return
            if type(args) is not dict:
                self.sendError(txn_id, (203, "bad args type"))
                return
            self.handleQuery(txn_id, query_name, args)

        elif msg_type == b'r':
            deferred = self.open_queries.pop(txn_id, None)
            if deferred is None or b'r' not in args:
                # probably best to give this node a healthy bit of distance
                self.transport.loseConnection()
                return

            self.log.info("Query response (txn {txn}): {args}", txn=txn_id, args=krpc[b'r'])
            deferred.callback(args)

        elif msg_type == b'e':
            try:
                errcode, errinfo = krpc[b'e']
                assert type(errcode) is int
                assert type(errinfo) is bytes
                errinfo = errinfo.decode("UTF-8")
            except TypeError, AssertionError:
                errcode, errinfo = None, None

            self.log.info("Error response on txn {txn}. code: {code}, info: {info}",
                          txn=txn_id, code=errcode, info=errinfo)

            if txn_id in self.open_queries:
                self.log.debug("Firing errback with {errtype}",
                               errtype=errcodes.get(errcode, TheseusProtocolError))
                self.open_queries.pop(txn_id).errback(
                        errcodes.get(errcode, TheseusProtocolError)(errinfo)
                        )
            else:
                self.log.info("txn id {txn} for error unrecognized", txn=txn_id)

    def handleQuery(self, txn_id, query_name, args):
        if query_name not in self.query_handlers:
            self.log.info("Unsupported query {name} requested in {proto}", name=query_name, proto=self)
            self.sendError(txn_id, (204, "query not supported"))
            return

        try:
            # event callback for subclasses
            self.onQuery(txn_id, query_name, args)
        except TheseusProtocolError as e:
            errtup = (e.errcode, ''.join(e.args) or e.error_name)
            self.sendError(txn_id, errtup)
            self.log.warn("Error in query event callback -- sending {errtup}", errtup=errtup)
            self.log.debug("Traceback: {tb}", tb=traceback.format_exc())
            return

        self.log.debug("Attempting to generate response to query (txn {txn}): {query_name} {args}",
                       txn=txn_id, query_name=query_name, args=args)
        try:
            result = self.query_handlers[query_name](args)
            assert type(result) in (dict, Deferred)

            if type(result) is Deferred:
                def query_callback(val):
                    self.log.debug("Query callback for {name} (txn {txn_id}) triggered! args={args}, callback value={val}",
                                   name=query_name, txn_id=txn_id, args=args, val=val)
                    self.handleQuery(txn_id, query_name, args)
                    return val

                self.deferred_responses[txn_id] = (query_name, args, result)
                result.addCallback(query_callback)
                self.log.debug("Deferring response in txn {txn_id}", txn_id=txn_id)
            else:  # type(result) is dict:
                self.deferred_responses.pop(txn_id, None)
                self.sendResponse(txn_id, result)

        except BencodeError:
            self.sendError(txn_id, (202, "internal error"))
            self.log.error("Internal error trying to bencode the following response (txn {txn}): {result}",
                           txn=txn_id, result=result)

        except AssertionError:
            message = result if type(result) is str else "query failed"
            self.sendError(txn_id, (201, message))
            self.log.info("Error 201 ({msg}) (txn {txn})", msg=message, txn=txn_id)

        except Exception as e:
            self.sendError(txn_id, (202, "internal error"))
            self.log.debug("Traceback: {tb}", tb=traceback.format_exc())
            self.log.error("Unhandled error responding to query {name} (txn {txn}): {err}",
                           name=query_name, txn=txn_id, err=e)

    def onQuery(self, txn_id, query_name, args):
        """
        To be overridden in subclasses wishing to hook the query event. Raise a
        TheseusProtocolError in this function to abort the query and send the
        same error code, along with any arguments passed to the
        TheseusProtocolError, to the remote node.
        """

    def onError(self, failure):
        """
        To be overridden in subclasses wishing to hook the error event.
        """
        return failure

    def sendQuery(self, query_name, args):
        if type(query_name) is str:
            query_name = query_name.encode("ascii")  # normalizing type for the dict key

        txn_id = os.urandom(2)
        self.log.info("Sending query (txn {txn}): {query} {args}", txn=txn_id, query=query_name, args=args)
        self.sendString(bencode({b't': txn_id, b'y': b'q', b'q': query_name, b'a': args}))

        deferred = Deferred()
        if query_name in self.response_handlers:
            deferred.addCallback(self.response_handlers.get(query_name))
        deferred.addErrback(self.onError)

        self.open_queries[txn_id] = deferred
        return deferred

    def sendResponse(self, txn_id, retval):
        response = {b't': txn_id, b'y': b'r', b'r': retval}
        bencoded = bencode(response)
        self.log.info("Sending query response: {response} (bencode: {bencoded})", response=response, bencoded=bencoded)
        self.sendString(bencoded)

    def sendError(self, txn_id, errtup):
        self.log.info("Sending error: {err}", err=errtup)
        self.sendString(bencode({b't': txn_id, b'y': b'e', b'e': errtup}))

    def sendString(self, string):
        self.log.debug("Sending string: {string}", string=string)
        super().sendString(string)
