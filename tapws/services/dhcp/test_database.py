import unittest
import unittest.mock
from .database import Database
import asyncio


class TestDatabase(unittest.TestCase):
    def setUp(self) -> None:
        import logging

        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger().handlers.clear()
        self.db = Database(3600)
        return super().setUp()

    def testAddRemoveLease(self):
        lease = unittest.mock.Mock(ip="1.2.3.4", mac=b"abcdef")
        self.db.add_lease(lease)
        self.assertEqual(self.db.get_lease(b"abcdef"), lease)
        self.db.remove_lease(lease)
        self.assertIsNone(self.db.get_lease(b"abcdef"))

        ## test remove unknown lease
        self.db.is_debug = True
        self.db.remove_lease(lease)
        self.assertIsNone(self.db.get_lease(b"abcdef"))

    def testRenewLease(self):
        lease = unittest.mock.Mock(ip="1.2.3.4", mac=b"abcdef")

        def fake_renew(expiry: int):
            lease.expiry = expiry

        lease.expiry = 1
        lease.renew = fake_renew
        self.db.add_lease(lease)
        self.db.renew_lease(lease)

        self.assertEqual(lease.expiry, 3600)
        self.db.remove_lease(lease)

        # test renew non-existent lease
        self.db.renew_lease(lease)

    def testExpiredLeasesAsync(self):
        lease = unittest.mock.Mock(ip="2.3.4.5", mac=b"bcdefg", expired=True)
        self.db.add_lease(lease)

        async def test_expired():
            result = []
            async for l in self.db.expired_leases():
                result.append(l)
            self.assertEqual(result, [lease])

        asyncio.run(test_expired())
        self.db.remove_lease(lease)

    def testIpAvailable(self):
        lease = unittest.mock.Mock(ip=123, mac=b"bcdefg", expired=True)
        self.db.add_lease(lease)
        self.assertFalse(self.db.is_ip_available(123))
