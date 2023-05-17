from .utils import format_mac
import unittest
import unittest.mock


class TestFormatMAC(unittest.TestCase):
    def testMAC(self):
        result = b"00:00:00:00:00:00"
        with unittest.mock.patch("macaddress.MAC", return_value=result):
            self.assertEqual(format_mac(result), str(result))

    def testRaisesValueError(self):
        with unittest.mock.patch(
            "macaddress.MAC", side_effect=ValueError("invalid value")
        ):
            with self.assertRaises(ValueError):
                format_mac(b"invalid input")
