#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
from functools import partial, wraps

import websockets

from .device import create_tap_device


def wrap_async(func):

    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run


class Server:

    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.CLIENTS = set()
        self.tap = create_tap_device()
        self.tap.up()

    async def broadcast(self, message):
        logging.debug("broadcast message!")
        for client in self.CLIENTS:
            await client.send(message)

    @wrap_async
    def tap_read(self):
        return self.tap.read(self.tap.mtu)

    @wrap_async
    def tap_write(self, message):
        self.tap.write(message)

    async def websocket_handler(self, websocket, path):
        self.websocket_add_client(websocket, path)

        try:
            remote_ip = websocket.remote_address[0]
            logging.info(f"{remote_ip} connected")
            async for message in websocket:
                logging.debug("writing to tap device")
                await self.tap_write(message)
        except websockets.exceptions.ConnectionClosed as e:
            self.websocket_remove_client(websocket, path)
            logging.debug(f"{remote_ip} disconnected")
        except Exception as e:
            logging.error(e)

    def websocket_add_client(self, websocket, path):
        self.CLIENTS.add(websocket)

    def websocket_remove_client(self, websocket, path):
        self.CLIENTS.remove(websocket)

    async def device_worker(self):
        logging.info("from device worker")
        while True:
            message = await self.tap_read()
            logging.debug(f"Total clients: {len(self.CLIENTS)}")
            logging.debug(f"Broadcasting message: {message}")
            if len(self.CLIENTS):
                await self.broadcast(message)

    async def start(self):
        await asyncio.gather(
            self.device_worker(),
            websockets.serve(self.websocket_handler, self.host, self.port))
