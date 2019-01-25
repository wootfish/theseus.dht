from twisted.trial import unittest

from theseus.datastore import DataStore
from theseus.constants import L


class DataStoreTests(unittest.TestCase):
    def _cleanup(self, data_store):
        if data_store.looper.running:
            data_store.looper.stop()

    def test_init(self):
        ds2_local_addr = bytes(L//8)
        ds3_memlimit = 2**16
        ds4_default_duration = 10

        ds = DataStore()
        ds2 = DataStore(local_addr=ds2_local_addr)
        ds3 = DataStore(memlimit=ds3_memlimit)
        ds4 = DataStore(default_duration=ds4_default_duration)

        for store in (ds, ds2, ds3, ds4):
            self.addCleanup(self._cleanup, store)

        self.assertEqual(ds.local_addr, None)
        self.assertEqual(ds.memlimit, DataStore.memlimit)
        self.assertEqual(ds.default_duration, DataStore.default_duration)

        self.assertEqual(ds2.local_addr, ds2_local_addr)
        self.assertEqual(ds2.memlimit, DataStore.memlimit)
        self.assertEqual(ds2.default_duration, DataStore.default_duration)

        self.assertEqual(ds3.local_addr, None)
        self.assertEqual(ds3.memlimit, ds3_memlimit)
        self.assertEqual(ds3.default_duration, DataStore.default_duration)

        self.assertEqual(ds4.local_addr, None)
        self.assertEqual(ds4.memlimit, DataStore.memlimit)
        self.assertEqual(ds4.default_duration, ds4_default_duration)

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

        ds.put(addr3, b'howdy', tags={b'hey': b'ho'})
        self.assertEqual(ds.get(), {addr1: [b'hi'], addr2: [b'hello']})
        self.assertEqual(ds.get(tag_names=[b'hey']), {addr3: [[b'howdy', b'ho']]})
        self.assertEqual(ds.get(addr1), [b'hi'])
        self.assertEqual(ds.get(addr2), [b'hello'])
        self.assertEqual(ds.get(addr3, [b'hey']), [[b'howdy', b'ho']])
