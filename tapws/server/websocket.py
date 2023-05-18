#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import ssl
import typing
import logging
from websockets import exceptions as websockets_exceptions
from websockets.server import WebSocketServerProtocol, WebSocketServer, serve as Serve
from .connection import Connection
from ..utils import format_mac


class WebSocket(object):
    connections: typing.Set[Connection]
    ws_server: typing.Optional[WebSocketServer]
    on_message: typing.Callable

    def __init__(
        self,
        on_message_callback: typing.Callable,
        host: str,
        port: int,
        *,
        ssl: typing.Optional[ssl.SSLContext] = None,
        logger: logging.Logger = logging.getLogger("tapws.websocket"),
        ws_factory_cls: typing.Type[Serve] = Serve,
    ) -> None:
        self.connections = set()
        self.on_message = on_message_callback
        self.logger = logger
        self.ws_factory = ws_factory_cls(self.handler, host, port, ssl=ssl)
        self.ws_server = None

        # refs: https://www.iana.org/assignments/ethernet-numbers/ethernet-numbers.xhtml
        self.broadcast_addr = "ff:ff:ff:ff:ff:ff"
        self.whitelist_macs = (
            "33:33:",
            "01:00:5e:",
            "00:52:02:",
        )

    def broadcast(self, message: bytes):
        dst_mac = format_mac(message[:6])

        for connection in self.connections:
            if dst_mac in (
                self.broadcast_addr,
                connection.mac,
            ) or dst_mac.startswith(self.whitelist_macs):
                asyncio.create_task(
                    connection.websocket.send(message=message), name="broadcast"
                )

    async def start(self):
        self.ws_server = await self.ws_factory

    async def stop(self):
        if self.ws_server:
            self.ws_server.close()
            await self.ws_server.wait_closed()
        self.ws_server = None

    async def handler(self, websocket: WebSocketServerProtocol):
        connection = Connection(websocket, None)
        self.connections.add(connection)

        try:
            async for message in websocket:
                mac = format_mac(message[6:12])  # type: ignore
                connection.mac = mac
                await self.on_message(message)
        except websockets_exceptions.ConnectionClosed as e:
            self.logger.info(f"Client disconnected: {e}")
        except Exception as e:
            self.logger.error(f"Unknown exception raised: {e}")
        finally:
            self.connections.remove(connection)
