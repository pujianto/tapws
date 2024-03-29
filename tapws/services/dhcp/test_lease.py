import unittest
from .lease import Lease


class TestLease(unittest.TestCase):
    def setUp(self) -> None:
        self.lease = Lease(b"abcdef", 123, 1)
        return super().setUp()

    def testRenew(self):
        self.lease.renew(1000)
        self.assertEqual(self.lease.lease_time, 1000)
        lease_repr = "Lease(61:62:63:64:65:66, 0.0.0.123, 1000)"
        self.assertEqual(str(self.lease), lease_repr)

    def testRenewInvalid(self):
        with self.assertRaises(ValueError):
            self.lease.renew(0)

    def testIsExpired(self):
        self.lease.lease_time = -10

        self.assertTrue(self.lease.expired)

    def testIsNotExpired(self):
        self.lease.lease_time = 100
        self.assertFalse(self.lease.expired)

    def testLeaseNeverExpired(self):
        self.lease.lease_time = -1
        self.assertFalse(self.lease.expired)
