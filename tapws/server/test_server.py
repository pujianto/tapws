#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import unittest.mock
from .server import Server, ServerConfig
import asyncio
import typing


class TestServer(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.tuntap = unittest.mock.AsyncMock()
        self.tuntap_wrapper = unittest.mock.Mock(side_effect=[self.tuntap])
        self.tuntap.fileno = unittest.mock.mock_open()
        self.tuntap.read = unittest.mock.Mock(return_value=b"mmmmmmmmmm")

        self.fake_ws_serve = unittest.mock.AsyncMock()
        self.fake_ws_serve.close = lambda: None
        self.fake_ws_serve.broadcast = self.broadcast_helper
        self.fake_ws_cls = unittest.mock.Mock(side_effect=[self.fake_ws_serve])

    def broadcast_helper(self, message: bytes):
        self.read_message = message

    async def testBroadcast(self):
        def mock_reader(_: typing.Any, fd: int, callback: typing.Callable, *args):
            callback()

        with unittest.mock.patch(
            "asyncio.unix_events._UnixSelectorEventLoop.add_reader",
            mock_reader,
        ):
            s = Server(
                ServerConfig.From_env(),
                services=[],
                tuntap_wrapper=self.tuntap_wrapper,  # type: ignore
                websocket_wrapper=self.fake_ws_cls,  # type: ignore
            )

            await s.start()
            self.assertEqual(self.read_message, b"mmmmmmmmmm")
            await s.stop()

    async def testStartStop(self):
        services = [unittest.mock.AsyncMock()]

        s = Server(
            ServerConfig.From_env(),
            services=services,  # type: ignore
            tuntap_wrapper=self.tuntap_wrapper,  # type: ignore
            websocket_wrapper=self.fake_ws_cls,  # type: ignore
        )

        await s.start()
        self.assertFalse(s._waiter_.done())
        await s.stop()
        self.assertTrue(s._waiter_.done())

    async def testLoadWithAsyncWith(self):
        s = Server(
            ServerConfig.From_env(),
            tuntap_wrapper=self.tuntap_wrapper,  # type: ignore
            websocket_wrapper=self.fake_ws_cls,  # type: ignore
        )
        async with s as sw:
            self.assertIsInstance(sw._waiter_, asyncio.Future)

    async def testCallWithAwait(self):
        async def _helper_stop_instance(instance: Server):
            self.assertFalse(instance._waiter_.done())
            await asyncio.sleep(0.01)
            await instance.stop()
            self.assertTrue(instance._waiter_.done())

        s = Server(
            ServerConfig.From_env(),
            tuntap_wrapper=self.tuntap_wrapper,  # type: ignore
            websocket_wrapper=self.fake_ws_cls,  # type: ignore
        )

        asyncio.create_task(_helper_stop_instance(s))
        await s
