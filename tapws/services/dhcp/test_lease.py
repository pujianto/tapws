import unittest
from .lease import Lease


class TestLease(unittest.TestCase):
    def setUp(self) -> None:
        self.lease = Lease(b"abcdefg", 123, 1)
        return super().setUp()

    def testRenew(self):
        self.lease.renew(1000)
        self.assertEqual(self.lease.lease_time, 1000)

    def testRenewInvalid(self):
        with self.assertRaises(ValueError):
            self.lease.renew(0)

    def testIsExpired(self):
        self.lease.lease_time = -10

        self.assertTrue(self.lease.expired)

    def testIsNotExpired(self):
        self.lease.lease_time = 2
        self.assertFalse(self.lease.expired)

    def testLeaseNeverExpired(self):
        self.lease.lease_time = -1
        self.assertFalse(self.lease.expired)
