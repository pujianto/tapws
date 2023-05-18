#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import unittest.mock
from .websocket import WebSocket


class TestWebSocket(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        ws_server = unittest.mock.AsyncMock()
        ws_server.close = self.sync_helper
        self.ws_factory = unittest.mock.AsyncMock(side_effect=[ws_server])

        self.ws = WebSocket(
            self.callback_helper,
            "0.0.0.0",
            123,
            ws_factory_cls=self.ws_factory,  # type: ignore
        )

    def sync_helper(self):
        return None

    def callback_helper(self, message: bytes):
        pass

    async def testStartStop(self):
        self.assertIsNone(self.ws.ws_server)
        await self.ws.start()
        self.assertIsNotNone(self.ws.ws_server)
        await self.ws.stop()
        self.assertIsNone(self.ws.ws_server)
