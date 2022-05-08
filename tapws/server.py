#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import signal
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

    def __init__(self, host='0.0.0.0', port=8080, device=None):
        self.host = host
        self.port = port
        self.CLIENTS = set()
        if device is None:
            device = create_tap_device()
            device.up()
        self.tap = device
        self.ws_server = websockets.serve(self.websocket_handler, self.host,
                                          self.port)

    async def broadcast(self, message):
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
            async for message in websocket:
                await self.tap_write(message)
        except websockets.exceptions.ConnectionClosed as e:
            self.websocket_remove_client(websocket, path)
        except Exception as e:
            logging.error(e)

    def websocket_add_client(self, websocket, path):
        self.CLIENTS.add(websocket)

    def websocket_remove_client(self, websocket, path):
        self.CLIENTS.remove(websocket)

    def cleanup(self, *args, **kwargs):
        logging.info('Attempting to stop server...')
        self.terminate = True

    async def device_worker(self):
        while not self.terminate:
            message = await self.tap_read()
            logging.debug(f"Total clients: {len(self.CLIENTS)}")
            logging.debug(f"Broadcasting message: {message}")
            if len(self.CLIENTS):
                await self.broadcast(message)
            if self.terminate:
                break

    async def start(self):
        logging.info('Starting server...')
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.cleanup, sig)

        self.terminate = False
        await asyncio.gather(self.ws_server, self.device_worker())
        self.tap.close()
