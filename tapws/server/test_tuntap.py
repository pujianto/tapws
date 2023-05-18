#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import unittest.mock
import typing
from .tuntap import TuntapWrapper, TunError


class MockDevice(unittest.mock.Mock):
    def __init__(self, *args: typing.List, **kwargs: typing.Dict) -> None:
        super().__init__(*args, **kwargs)
        self.msg = None

    def write(self, message: bytes):
        self.msg = message


class TestTuntapWrapper(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        fake_dev = MockDevice()
        fake_dev.fileno.return_value = 123
        self.message = b"message"
        fake_dev.read.return_value = self.message
        wrapper = unittest.mock.Mock(return_value=fake_dev)
        self.instance = TuntapWrapper("i", "", "", 0, device_cls=wrapper)
        return super().setUp()

    def testRead(self):
        self.assertEqual(self.instance.read(), self.message)

    def testFileno(self):
        self.assertEqual(self.instance.fileno(), 123)

    def testWrite(self):
        message = b"msg"
        self.instance.write(message)
        self.assertEqual(message, self.instance.device.msg)

    async def testStartStop(self):
        await self.instance.start()
        self.assertTrue(self.instance.is_up)
        await self.instance.stop()
        self.assertFalse(self.instance.is_up)

    async def testAwrite(self):
        await self.instance.awrite(b"msg")
        self.assertEqual(b"msg", self.instance.device.msg)

    def testWriteError(self):
        with unittest.mock.patch.object(
            self.instance.device, "write", unittest.mock.Mock(side_effect=[TunError()])
        ):
            self.instance.write(b"test")
            self.assertNotEqual(self.instance.device.msg, b"test")

    def testTunError(self):
        with self.assertRaises(TunError):
            device = unittest.mock.Mock(side_effect=[TunError(2, "msg")])
            TuntapWrapper("a", "", "", 0, device_cls=device)
