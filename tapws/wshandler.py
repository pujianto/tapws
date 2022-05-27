#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
from asyncio.futures import Future
from functools import partial
from typing import Set, Tuple

import aiohttp_jinja2
from aiohttp import web
from pytun import Error as TunError
from pytun import TunTapDevice

from .connection import Connection
from .utils import format_mac


class WebsocketHandler:
    __slots__ = ("connections", "device", "logger", "is_debug", "routes", "hw_addr")
    connections: Set[Connection]
    broadcast_addr: str = "ff:ff:ff:ff:ff:ff"
    whitelist_macs: Tuple = ("33:33:", "01:00:5e:", "00:52:02:")

    def __init__(self, device: TunTapDevice) -> None:
        self.device = device
        self.connections = set()
        self.logger = logging.getLogger("tapws.websockethandler")
        self.is_debug = self.logger.isEnabledFor(logging.DEBUG)
        self.routes = [
            web.get("/", self.web_handler),
            web.get("/ws", self.handler),
        ]
        self.hw_addr = format_mac(self.device.hwaddr)

    async def handler(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        connection = Connection(ws, None)
        self.connections.add(connection)
        try:
            async for message in ws:
                if message.type == web.WSMsgType.BINARY:
                    mac = format_mac(message.data[6:12])
                    connection.mac = mac
                    self.logger.debug(f"MAC: {mac}")
                    try:
                        self.device.write(message.data)
                    except TunError as e:
                        self.logger.error(f"Error writing to device: {e}")
                    except Exception as e:
                        self.logger.error(f"Unknown error writing to device: {e}")

        except ValueError as e:
            self.logger.warning(f"Invalid mac: {e}")
        finally:
            self.connections.remove(connection)
        return ws

    async def web_handler(self, request: web.Request) -> web.Response:

        context = {
            "hw_addr": self.hw_addr,
            "debug": self.is_debug,
        }

        response = aiohttp_jinja2.render_template("index.html", request, context)
        return response

    def broadcast(self):
        message = self.device.read(1024 * 4)
        dst_mac = format_mac(message[:6])
        for connection in self.connections:
            if connection.websocket.closed:
                continue
            try:
                if self.is_debug:
                    self.logger.debug(
                        f"Sending to {dst_mac} | connection: {connection.mac} | hwaddr: {self.hw_addr}"
                    )

                if dst_mac in [self.broadcast_addr, connection.mac]:
                    asyncio.create_task(
                        connection.websocket.send_bytes(message), name="send"
                    ).add_done_callback(partial(self._on_send_done))
                    continue

                if dst_mac.startswith(self.whitelist_macs):
                    asyncio.create_task(
                        connection.websocket.send_bytes(message), name="send"
                    ).add_done_callback(partial(self._on_send_done))
                    continue

            except Exception as e:
                self.logger.warning(f"Error broadcasting message to client: {e}")

    def _on_send_done(self, future: Future) -> None:
        if future.exception():
            self.logger.warning(
                f"Error sending message to client: {future.exception()}"
            )
