from .utils import format_mac
import unittest


class TestFormatMAC(unittest.TestCase):
    def testMAC(self):
        self.assertEqual(format_mac(b"abcdef"), "61:62:63:64:65:66")

    def testRaisesValueError(self):
        with self.assertRaises(ValueError):
            format_mac(b"invalid input")
