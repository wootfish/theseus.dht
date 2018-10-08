from twisted.trial import unittest

from theseus.datastore import DataStore
from theseus.constants import L


class DataStoreTests(unittest.TestCase):
    def _cleanup(self, data_store):
        if data_store.looper.running:
            data_store.looper.stop()

    def test_init(self):
        ds = DataStore()
        ds2 = DataStore(local_addr=bytes(L//8))
        ds3 = DataStore(memlimit=2**16)
        ds4 = DataStore(default_duration=10)

        for store in (ds, ds2, ds3, ds4):
            self.addCleanup(self._cleanup, store)

        self.assertEqual(ds.local_addr, None)
        self.assertEqual(ds.memlimit, DataStore.memlimit)
        self.assertEqual(ds.default_duration, DataStore.default_duration)

        self.assertEqual(ds2.local_addr, bytes(L//8))
        self.assertEqual(ds2.memlimit, DataStore.memlimit)
        self.assertEqual(ds2.default_duration, DataStore.default_duration)

        self.assertEqual(ds3.local_addr, None)
        self.assertEqual(ds3.memlimit, 2**16)
        self.assertEqual(ds3.default_duration, DataStore.default_duration)

        self.assertEqual(ds4.local_addr, None)
        self.assertEqual(ds4.memlimit, DataStore.memlimit)
        self.assertEqual(ds4.default_duration, 10)

    def test_basic_io(self):
        addr1 = bytes(L//8)
        addr2 = b'\x17'*(L//8)
        addr3 = b'\x34'*(L//8)

        ds = DataStore()
        self.addCleanup(self._cleanup, ds)

        ds.put(addr1, b'hi')
        ds.put(addr2, b'hello')

        self.assertEqual(ds.get(), {addr1: [b'hi'], addr2: [b'hello']})
        self.assertEqual(ds.get(addr1), [b'hi'])
        self.assertEqual(ds.get(addr2), [b'hello'])
        self.assertEqual(ds.get(addr3), [])
