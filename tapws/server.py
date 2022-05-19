#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
from asyncio import create_task
from functools import partial
from typing import Optional

from pytun import IFF_NO_PI, IFF_TAP
from pytun import Error as TunError
from pytun import TunTapDevice
from websockets import exceptions as websockets_exceptions
from websockets.server import WebSocketServerProtocol
from websockets.server import serve as websockets_serve

from tapws.services.dhcp.config import DHCPConfig
from tapws.services.dhcp.server import DHCPServer
from tapws.services.netfilter.netfilter import Netfilter

from .config import ServerConfig
from .utils import format_mac


class Connection:

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

    def __init__(
        self,
        config: ServerConfig,
    ) -> None:
        self.config = config
        self._connections = set()
        self.tap = TunTapDevice(self.config.private_interface,
                                flags=(IFF_TAP | IFF_NO_PI))
        self.tap.addr = str(self.config.intra_ip)
        self.tap.netmask = str(self.config.intra_network.netmask)
        self.tap.mtu = 1500
        self.hw_addr = format_mac(self.tap.hwaddr)

        if self.config.enable_dhcp:
            dhcp_config = DHCPConfig(
                server_ip=self.config.intra_ip,
                server_network=self.config.intra_network,
                server_router=self.config.router_ip,
                dns_ips=self.config.dns_ips,
                lease_time_second=self.config.dhcp_lease_time,
                bind_interface=self.config.private_interface,
            )
            self.dhcp_svc = DHCPServer(dhcp_config)
        if self.config.public_interface:
            self.netfilter_svc = Netfilter(
                public_interface=self.config.public_interface,
                private_interface=self.config.private_interface)

        self.loop = asyncio.get_running_loop()

        # refs: https://www.iana.org/assignments/ethernet-numbers/ethernet-numbers.xhtml
        self.broadcast_addr = 'ff:ff:ff:ff:ff:ff'
        self.whitelist_macs = ('33:33:', '01:00:5e:', '00:52:02:')

        logger = logging.getLogger('tapws')
        self.is_debug = logger.isEnabledFor(logging.DEBUG)
        self.logger = logger

    def broadcast(self) -> None:
        message = self.tap.read(1024 * 4)
        dst_mac = format_mac(message[:6])

        for connection in self._connections.copy():
            try:
                if self.is_debug:
                    self.logger.debug(
                        f'Sending to {dst_mac} | connection: {connection.mac} | hwaddr: {self.hw_addr}'
                    )

                if dst_mac in [self.broadcast_addr, connection.mac]:
                    create_task(connection.websocket.send(message))
                    continue

                if dst_mac.startswith(self.whitelist_macs):
                    create_task(connection.websocket.send(message))
                    continue

            except Exception as e:
                self.logger.warning(
                    f'Error broadcasting message to client: {e}')

    async def websocket_handler(self,
                                websocket: WebSocketServerProtocol) -> None:
        connection = Connection(websocket, None)
        self._connections.add(connection)
        try:
            async for message in websocket:
                mac = format_mac(message[6:12])
                if self.is_debug:
                    self.logger.info(
                        f'incoming from {mac} | hwaddr: {self.hw_addr}')
                connection.mac = mac
                try:
                    self.tap.write(message)
                except TunError as e:
                    self.logger.error(f'Error writing to device: {e}')
                except Exception as e:
                    self.logger.error(f'Unknown error writing to device: {e}')

        except websockets_exceptions.ConnectionClosed as e:
            self.logger.info(f'Client disconnected: {e}')
        except Exception as e:
            self.logger.error(e)
        finally:
            self._connections.remove(connection)

    async def start(self) -> None:
        self.tap.up()
        self.logger.info('Starting service...')

        self.loop.add_reader(self.tap.fileno(), partial(self.broadcast))

        ws = websockets_serve(self.websocket_handler,
                              self.config.host,
                              self.config.port,
                              ssl=self.config.ssl)

        self.ws_server = await ws
        if self.config.enable_dhcp:
            await self.dhcp_svc.start()
        if self.config.public_interface:
            await self.netfilter_svc.start()

        self.logger.info(
            f'Service running on {self.config.host}:{self.config.port}')

        await self.ws_server.wait_closed()

    async def stop(self) -> None:

        self.logger.info('Stopping service...')
        if self.config.enable_dhcp:
            await self.dhcp_svc.stop()
        if self.config.public_interface:
            await self.netfilter_svc.stop()

        self.ws_server.close()
        self.tap.close()
