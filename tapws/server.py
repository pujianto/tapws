#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import signal
from functools import partial

import websockets
from pytun import Error as TunError

from .device import create_tap_device
from .utils import async_iter, wrap_async


class Server:

    def __init__(self, host='0.0.0.0', port=8080, device=None, ssl=None):
        self.host = host
        self.port = port
        self.CLIENTS = set()
        if device is None:
            device = create_tap_device()
            device.up()
        self.tap = device
        self.ws_server = websockets.serve(self.websocket_handler,
                                          self.host,
                                          self.port,
                                          ssl=ssl)
        self.waiter = asyncio.Future()

    async def broadcast(self, message):
        async for client in async_iter(self.CLIENTS):
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                logging.debug('client disconnected')
            except Exception as e:
                logging.error(f'Error broadcasting message to client: {e}')

    def tap_read(self):
        try:
            message = self.tap.read(1024 * 4)
            asyncio.create_task(self.broadcast(message))
        except TunError as e:
            logging.error(f'Error reading from device: {e}')
        except Exception as e:
            logging.error(f'Unknown error reading from device: {e}')

    @wrap_async
    def tap_write_async(self, message):
        try:
            self.tap.write(message)
        except TunError as e:
            logging.error(f'Error writing to device: {e}')
        except Exception as e:
            logging.error(f'Unknown error writing to device: {e}')

    async def websocket_handler(self, websocket):
        self.websocket_add_client(websocket)
        try:
            async for message in websocket:
                await self.tap_write_async(message)

        except websockets.exceptions.ConnectionClosed as e:
            logging.debug(f'Client disconnected: {e}')
        except Exception as e:
            logging.error(e)
        finally:
            self.websocket_remove_client(websocket)

    def websocket_add_client(self, websocket):
        self.CLIENTS.add(websocket)

    def websocket_remove_client(self, websocket):
        self.CLIENTS.remove(websocket)

    def cleanup(self, sig):
        asyncio.create_task(self.stop())

    async def start(self):
        logging.info('Starting server...')
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.cleanup, sig)

        loop.add_reader(self.tap.fileno(), partial(self.tap_read))

        async with self.ws_server:
            await self.waiter
        self.tap.close()

    async def stop(self):
        self.waiter.set_result(None)
