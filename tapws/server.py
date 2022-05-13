#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
from functools import partial

import websockets
from pytun import IFF_MULTI_QUEUE, IFF_NO_PI, IFF_TAP
from pytun import Error as TunError
from pytun import TunTapDevice

from .utils import format_mac


class Connection:

    def __init__(self, websocket, mac=None):
        self.mac = mac
        self.websocket = websocket

    def __repr__(self):
        return f'Connection({self.websocket.id})'


class Server:

    def __init__(self,
                 host='0.0.0.0',
                 port=8080,
                 ssl=None,
                 services=[],
                 **kwargs):
        self.host = host
        self.port = port

        self.tap = TunTapDevice('tap0', flags=(IFF_TAP | IFF_NO_PI | IFF_MULTI_QUEUE))
        self.tap.addr = kwargs.get('ip', '10.11.12.1')

        self.tap.netmask = kwargs.get('netmask', '255.255.255.0')
        self.tap.mtu = kwargs.get('mtu', 1500)
        self.hw_addr = format_mac(self.tap.hwaddr)
        self._services = services
        self._connections = set()
        self.ssl = ssl
        self.loop = kwargs.get('loop', asyncio.get_running_loop())
        # refs: https://www.iana.org/assignments/ethernet-numbers/ethernet-numbers.xhtml
        self.broadcast_addr = 'ff:ff:ff:ff:ff:ff'
        self.whitelist_macs = ('33:33:', '01:00:5e:', '00:52:02:')

    def broadcast(self):
        message = self.tap.read(1024 * 4)
        dst_mac = format_mac(message[:6])
        for connection in self._connections.copy():
            try:
                logging.debug(
                    f'Sending to {dst_mac} | connection: {connection.mac} | hwaddr: {self.hw_addr}'
                )

                if dst_mac in [self.broadcast_addr, connection.mac]:
                    asyncio.create_task(connection.websocket.send(message))
                    continue

                if dst_mac.startswith(self.whitelist_macs):
                    return asyncio.create_task(connection.websocket.send(message))

            except Exception as e:
                logging.error(f'Error broadcasting message to client: {e}')

    async def websocket_handler(self, websocket):
        connection = Connection(websocket, None)
        self._connections.add(connection)
        try:
            async for message in websocket:
                mac = format_mac(message[6:12])
                logging.debug(
                    f'incoming from {mac} | connection: {connection.mac} | hwaddr: {self.hw_addr}'
                )
                connection.mac = mac
                try:
                    self.tap.write(message)
                except TunError as e:
                    logging.error(f'Error writing to device: {e}')
                except Exception as e:
                    logging.error(f'Unknown error writing to device: {e}')

        except websockets.exceptions.ConnectionClosed as e:
            logging.debug(f'Client disconnected: {e}')
        except Exception as e:
            logging.error(e)
        finally:
            self._connections.remove(connection)

    async def start(self):
        self.tap.up()
        logging.info('Starting service...')

        self.loop.add_reader(self.tap.fileno(), partial(self.broadcast))

        ws = websockets.serve(self.websocket_handler,
                              self.host,
                              self.port,
                              ssl=self.ssl)
        self.ws_server = await ws
        await self.ws_server.wait_closed()

    async def stop(self):
        for service in self._services:
            service.close()
        self.ws_server.close()
        self.tap.close()
