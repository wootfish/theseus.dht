from twisted.trial import unittest

from theseus.bencode import bencode, bdecode
from theseus.errors import BencodeError


class BencodeTests(unittest.TestCase):
    def test_bencode(self):
        self.assertEqual(bencode("abcdef"), b"6:abcdef")
        self.assertEqual(bencode({"bar": "spam", "foo": 42}), b"d3:bar4:spam3:fooi42ee")
        self.assertEqual(bencode([1, 2, 3, 4]), b"li1ei2ei3ei4ee")
        self.assertEqual(bencode({"foo": ["bar", "baz"], "numbers": {"1": 1, "2": "2", "3": 3, "4": "4"}, "seventeen": "lucky"}), b"d3:fool3:bar3:baze7:numbersd1:1i1e1:21:21:3i3e1:41:4e9:seventeen5:luckye")
        self.assertEqual(bencode(["Léon Theremin", "Kurt Gödel", "Paul Erdős"]), b"l14:L\xc3\xa9on Theremin11:Kurt G\xc3\xb6del11:Paul Erd\xc5\x91se")
        self.assertEqual(bencode({"a": 1, b"b": 2, b"c": 3, "d": 4}), b"d1:ai1e1:bi2e1:ci3e1:di4ee")

    def test_bdecode(self):
        self.assertEqual(bdecode(b"6:abcdef"), b"abcdef")
        self.assertEqual(bdecode("6:abcdef"), b"abcdef")
        self.assertEqual(bdecode(b"d3:bar4:spam3:fooi42ee"), {b"bar": b"spam", b"foo": 42})
        self.assertEqual(bdecode(b"li1ei2ei3ei4ee"), [1, 2, 3, 4])
        self.assertEqual(bdecode(b"d3:fool3:bar3:baze7:numbersd1:1i1e1:21:21:3i3e1:41:4e9:seventeen5:luckye"), {b"foo": [b"bar", b"baz"], b"numbers": {b"1": 1, b"2": b"2", b"3": 3, b"4": b"4"}, b"seventeen": b"lucky"})
        self.assertEqual(bdecode(b"l14:L\xc3\xa9on Theremin11:Kurt G\xc3\xb6del11:Paul Erd\xc5\x91se"), [b'L\xc3\xa9on Theremin', b'Kurt G\xc3\xb6del', b'Paul Erd\xc5\x91s'])

    def test_both(self):
        test_cases = (
                [1, 2, 3, 4, 5, 6, 7],
                b"the quick brown fox",
                {b"1": 1, b"2": 2, b"3": {b"4": 4, b"5": 5, b"6": {b"whoa": b"dude", b"dude": b"whoa", b"whhoa": b"whhhhoa"}}, b"seventeen": b"thirty-four"},
                [b"list", b"of", [b"lists"], [b"of lists", [b"and", b"lists", [b"within", b"lists"], b"listing", b"lists"], b"listlessly"]],
                )

        for case in test_cases:
            self.assertEqual(case, bdecode(bencode(case)))

    def test_errors(self):
        self.assertRaises(BencodeError, bencode, set())
        self.assertRaises(BencodeError, bencode, {1: 2, 3: 4})

        self.assertRaises(BencodeError, bdecode, b"")
        self.assertRaises(BencodeError, bdecode, b"something other than bencode")
        self.assertRaises(BencodeError, bdecode, b"d1:a1:b1:a1:be")
        self.assertRaises(BencodeError, bdecode, b"i12345")
        self.assertRaises(BencodeError, bdecode, b"12345e")
        self.assertRaises(BencodeError, bdecode, b"l")
        self.assertRaises(BencodeError, bdecode, b"d")
        self.assertRaises(BencodeError, bdecode, b"12:foo")
        self.assertRaises(BencodeError, bdecode, b"3:foobarbaz")
        self.assertRaises(BencodeError, bdecode, b"di1ei2ee")
