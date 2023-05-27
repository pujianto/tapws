#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import unittest
import unittest.mock
from websockets import exceptions as websockets_exceptions
from websockets import frames
from .websocket import WebSocket


class MockWsFactory(object):
    msg = b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xffzzzzz"

    def __init__(self, handler, *args, **kwargs):
        self.handler = handler

        self.m = MockWs(self.handler, self.msg)

    def __await__(self):
        return self.wait().__await__()

    async def wait(self):
        await self.m
        return self.m


class MockWs(object):
    def __init__(self, handler, msg, *args, **kwargs):
        self.msg = msg
        self.handler = handler

    async def mock_messages(self):
        yield self.msg

    async def mock_connection_closed(self):
        raise websockets_exceptions.ConnectionClosed(None, None)
        yield

    async def mock_unknown_exception(self):
        raise Exception("unknown")
        yield

    def __await__(self):
        tasks = []
        tasks.append(asyncio.create_task(self.handler(self.mock_connection_closed())))
        tasks.append(asyncio.create_task(self.handler(self.mock_unknown_exception())))
        tasks.append(asyncio.create_task(self.handler(self.mock_messages())))
        result = asyncio.gather(*tasks)
        yield from result

    async def wait_closed(self):
        ...

    def close(self):
        ...


class TestWebSocket(unittest.IsolatedAsyncioTestCase):
    async def callback_helper(self, message: bytes):
        self.assertEqual(MockWsFactory.msg, message)

    async def testStartStop(self):
        ws = WebSocket(
            self.callback_helper,
            "0.0.0.0",
            123,
            ws_factory_cls=MockWsFactory,
        )

        await ws.start()
        self.assertIsNotNone(ws.ws_server)
        conn = unittest.mock.AsyncMock()
        conn.mac = "ff:ff:ff:ff:ff:ff"
        with unittest.mock.patch.object(ws, "connections", [conn]):
            ws.broadcast(MockWsFactory.msg)
            conn.websocket.send.assert_called_once_with(message=MockWsFactory.msg)

        await ws.stop()
