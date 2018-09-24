from twisted.internet.error import ConnectionDone
from twisted.trial import unittest
from twisted.test import proto_helpers

from theseus.errors import TheseusProtocolError, BencodeError
from theseus.protocol import KRPCProtocol
from theseus.bencode import bencode, bdecode

from theseus.test.util import netstringify, unnetstringify


class TestKRPCProtocol(KRPCProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.remote_data = None
        #self.deferred = None
        self.count = 0

        self.query_handlers.update({
            b"echo": self.qEcho,
            b"info": self.qInfo,
            b"add": self.qAdd,
            #b"defer": self.qDefer
            })
        self.response_handlers.update({
            b"info": self.rInfo,
            })

    def qEcho(self, args):
        return args

    def qInfo(self, args):
        return {"info": "dolla dolla bill yall"}

    def qAdd(self, args):
        try:
            return {"sum": sum(args[b"nums"])}
        except KeyError:
            return "missing argument"
        except TypeError:
            return "unsummable arg provided"
        return "generic error"

    #def qDefer(self, args):
    #    if self.count < 3:
    #        self.count += 1
    #        self.deferred = Deferred()
    #        return self.deferred

    #    self.deferred = None
    #    return {"result": "we good"}

    def rInfo(self, args):
        self.remote_data = args.get(b"info")
        return args


class KRPCTests(unittest.TestCase):
    def setUp(self):
        self.proto = TestKRPCProtocol()
        self.transport = proto_helpers.StringTransportWithDisconnection()
        self.transport.protocol = self.proto
        self.proto.makeConnection(self.transport)

    def _test_query(self, query, expected_response):
        self.proto.stringReceived(bencode(query))
        self.assertEqual(self.transport.value(), netstringify(bencode(expected_response)))
        self.transport.clear()

    def test_query_handling(self):
        self._test_query(
                {"t": "17", "y": "q", "q": "echo", "a": {"arg1": 1, "arg2": 2}},
                {"t": "17", "y": "r", "r": {"arg1": 1, "arg2": 2}, }
                )

        self._test_query(
                {"t": "34", "y": "q", "q": "add", "a": {"nums": [1, 2, 3, 4]}},
                {"t": "34", "y": "r", "r": {"sum": 10}, }
                )

    def _start_info_query(self):
        d = self.proto.send_query("info", {"info": "cash rules everything around me"})
        actual = unnetstringify(self.transport.value(), self)
        self.transport.clear()

        txn = bdecode(actual)[b't']
        self.assertEqual(len(txn), 2)
        expected = bencode({
            b"t": txn,
            b"y": b"q",
            b"q": b"info",
            b"a": {b"info": b"cash rules everything around me"}
            })

        self.assertEqual(expected, actual)
        return d, txn

    def test_response_handling(self):
        d, txn = self._start_info_query()

        response = bencode({
            "t": txn,
            "y": "r",
            "r": {"info": "dolla dolla bill yall"}
            })

        self.proto.stringReceived(response)
        self.assertEqual(self.proto.remote_data, b"dolla dolla bill yall")
        return d

    def test_error_response_handling(self):
        d, txn = self._start_info_query()

        response = bencode({
            "t": txn,
            "y": "e",
            "e": (201, "oops!"),
            })

        self.proto.stringReceived(response)
        self.failureResultOf(d).trap(TheseusProtocolError)

    def test_malformed_error_response_handling(self):
        d, txn = self._start_info_query()

        response = bencode({
            "t": txn,
            "y": "e",
            "e": "not even a tuple, damn this is wrong",
            })

        self.proto.stringReceived(response)
        self.failureResultOf(d).trap(TheseusProtocolError)

    def test_bad_txn_error_response_handling(self):
        d, txn = self._start_info_query()

        new_txn = b'AA' if txn == b'ZZ' else b'ZZ'

        response = bencode({
            "t": new_txn,
            "y": "e",
            "e": "not even a tuple, damn this is wrong",
            })

        self.proto.stringReceived(response)
        # not really anything to assert here... we're more just looking to make
        # sure the code doesn't wig out

    def test_bad_response(self):
        d, txn = self._start_info_query()
        response = bencode({
            "t": txn,
            "y": "r"
            })
        self.proto.stringReceived(response)
        self.assertFalse(self.proto.transport.connected)
        self.failureResultOf(d).trap(Exception)

    def test_query_errors(self):
        # 'nums' key missing from 'add' query args
        self._test_query(
                {"t": "68", "y": "q", "q": "add", "a": {}},
                {"t": "68", "y": "e", "e": (100, "Generic KRPC error")}
                )

        # non-ints passed to 'add' query handler
        self._test_query(
                {"t": "85", "y": "q", "q": "add", "a": {"nums": (1, 2, 3, "oops")}},
                {"t": "85", "y": "e", "e": (100, "Generic KRPC error")}
                )

        # query with 'q' and 'a' keys missing
        self._test_query(
                {"t": "17", "y": "q"},
                {"t": "17", "y": "e", "e": (101, "Invalid KRPC message")}
                )

        # query 'a' arg mapped to non-dict
        self._test_query(
                {"t": "51", "y": "q", "q": "info", "a": "problem?"},
                {"t": "51", "y": "e", "e": (101, "Invalid KRPC message")}
                )

        # unsupported query name
        self._test_query(
                {"t": "34", "y": "q", "q": "nonesuch", "a": {}},
                {"t": "34", "y": "e", "e": (103, "Method not recognized")}
                )

    def test_internal_error_in_query_hook(self):
        def oh_no(*args):
            raise TheseusProtocolError("oh no!")
        self.proto.on_query = oh_no
        self._test_query(
                {"t": "17", "y": "q", "q": "echo", "a": {"arg1": 1, "arg2": 2}},
                {"t": "17", "y": "e", "e": (200, "oh no!")}
                )

    def test_internal_error_in_query_handler(self):
        def oh_no(*args):
            raise Exception("oh no!")
        self.proto.query_handlers[b"echo"] = oh_no
        self._test_query(
                {"t": "17", "y": "q", "q": "echo", "a": {"arg1": 1, "arg2": 2}},
                {"t": "17", "y": "e", "e": (200, "Generic DHT error")}
                )

    def test_bencode_error_in_query_responder(self):
        def oh_no(*args):
            raise BencodeError("oh no!")
        self.proto._send_response = oh_no
        self._test_query(
                {"t": "17", "y": "q", "q": "echo", "a": {"arg1": 1, "arg2": 2}},
                {"t": "17", "y": "e", "e": (102, "Internal error (KRPC)")}
                )

    #def test_deferred_response(self):
    #    self.proto.stringReceived(bencode(
    #        {"t": "17", "y": "q", "q": "defer", "a": {}}
    #        ))

    #    self.assertIsNot(self.proto.deferred, None)
    #    while self.proto.deferred is not None:
    #        self.proto.deferred.callback(None)

    #    self.assertEqual(self.transport.value(), netstringify(bencode(
    #        {"t": "17", "y": "r", "r": {"result": "we good"}}
    #        )))

    def test_errback_on_disconnect(self):
        d = self.proto.send_query("info", {"info": "smoke weed every day"})
        self.transport.loseConnection()
        self.failureResultOf(d).trap(ConnectionDone)

    def test_rejecting_nonsense(self):
        self.proto.stringReceived(b"it's like no cheese i've ever tasted")
        self.assertFalse(self.proto.transport.connected)
