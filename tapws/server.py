#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import ipaddress
import logging
import ssl
from asyncio import create_task
from functools import partial
from typing import List, Optional

from pytun import IFF_NO_PI, IFF_TAP
from pytun import Error as TunError
from pytun import TunTapDevice
from websockets import exceptions as websockets_exceptions
from websockets.server import WebSocketServerProtocol
from websockets.server import serve as websockets_serve

from .services.base import BaseService
from .utils import format_mac


class Connection:
    _mac = None

    def __init__(self,
                 websocket: WebSocketServerProtocol,
                 mac: Optional[str] = None) -> None:
        self._mac = mac
        self.websocket = websocket

    def __repr__(self) -> str:
        return f'Connection({self.websocket.id})'

    @property
    def mac(self) -> Optional[str]:
        return self._mac

    @mac.setter
    def mac(self, mac) -> None:
        self._mac = mac


class Server:
    _svcs = []

    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8080,
        ssl: Optional[ssl.SSLContext] = None,
        interface_name: str = 'tap0',
        interface_ip: str = '10.11.12.1',
        interface_subnet: int = 24,
        services: Optional[List[BaseService]] = None,
    ) -> None:

        self.host = host
        self.port = port

        self.iface_name = interface_name
        self.iface_ip = ipaddress.ip_address(interface_ip)
        self.iface_network = ipaddress.ip_network(
            f'{self.iface_ip}/{interface_subnet}', strict=False)

        self.tap = TunTapDevice(self.iface_name, flags=(IFF_TAP | IFF_NO_PI))
        self.tap.addr = str(self.iface_ip)
        self.tap.netmask = str(self.iface_network.netmask)
        self.tap.mtu = 1500
        self.hw_addr = format_mac(self.tap.hwaddr)

        if services is not None:
            self._svcs = services

        self._connections = set()
        self.ssl = ssl
        self.loop = asyncio.get_running_loop()
        # refs: https://www.iana.org/assignments/ethernet-numbers/ethernet-numbers.xhtml
        self.broadcast_addr = 'ff:ff:ff:ff:ff:ff'
        self.whitelist_macs = ('33:33:', '01:00:5e:', '00:52:02:')

    def broadcast(self) -> None:
        message = self.tap.read(1024 * 4)
        dst_mac = format_mac(message[:6])

        for connection in self._connections.copy():
            try:
                logging.debug(
                    f'Sending to {dst_mac} | connection: {connection.mac} | hwaddr: {self.hw_addr}'
                )

                if dst_mac in [self.broadcast_addr, connection.mac]:
                    create_task(connection.websocket.send(message))
                    continue

                if dst_mac.startswith(self.whitelist_macs):
                    create_task(connection.websocket.send(message))
                    continue

            except Exception as e:
                logging.error(f'Error broadcasting message to client: {e}')

    async def websocket_handler(self,
                                websocket: WebSocketServerProtocol) -> None:
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

        except websockets_exceptions.ConnectionClosed as e:
            logging.debug(f'Client disconnected: {e}')
        except Exception as e:
            logging.error(e)
        finally:
            self._connections.remove(connection)

    async def start(self) -> None:
        self.tap.up()
        logging.info('Starting service...')

        self.loop.add_reader(self.tap.fileno(), partial(self.broadcast))

        ws = websockets_serve(self.websocket_handler,
                              self.host,
                              self.port,
                              ssl=self.ssl)
        self.ws_server = await ws
        await self.ws_server.wait_closed()

    async def stop(self) -> None:

        for service in self._svcs:
            service.close()
        self.ws_server.close()
        self.tap.close()
