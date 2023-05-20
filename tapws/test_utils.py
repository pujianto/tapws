from .utils import format_mac, on_done
import unittest
import unittest.mock
import asyncio
import logging
from functools import partial


class TestFormatMAC(unittest.TestCase):
    def testMAC(self):
        self.assertEqual(format_mac(b"abcdef"), "61:62:63:64:65:66")

    def testRaisesValueError(self):
        with self.assertRaises(ValueError):
            format_mac(b"invalid input")


class TestOnDoneCallback(unittest.IsolatedAsyncioTestCase):
    async def exception_helper(self):
        async def inner():
            raise Exception("test exception")

        await inner()

    async def testRaisesException(self):
        logger = logging.getLogger("l")
        with unittest.mock.patch.object(
            logger, "warning"
        ) as mock_warning, self.assertRaises(Exception):
            f = self.exception_helper()
            asyncio.create_task(f).add_done_callback(partial(on_done, logger))
            mock_warning.assert_called_once()
