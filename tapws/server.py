#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
from asyncio import create_task
from asyncio.futures import Future
from functools import partial
from typing import Any, Generator, Set

from pytun import IFF_NO_PI, IFF_TAP
from pytun import Error as TunError
from pytun import TunTapDevice
from websockets import exceptions as websockets_exceptions
from websockets.server import WebSocketServerProtocol
from websockets.server import serve as websockets_serve

from .config import ServerConfig
from .connection import Connection
from .services.dhcp.config import DHCPConfig
from .services.dhcp.server import DHCPServer
from .services.netfilter import Netfilter
from .utils import format_mac


class Server:

    __slots__ = ('config', '_connections', 'is_debug', 'logger', 'tap', 'loop',
                 'hw_addr', 'broadcast_addr', 'whitelist_macs', 'dhcp_svc',
                 'netfilter_svc', 'ws_server', '_waiter_')
    _waiter_: Future[None]

    def __init__(
        self,
        config: ServerConfig,
    ) -> None:
        self.config = config
        self._connections: Set[Connection] = set()
        logger = logging.getLogger('tapws.main')
        self.is_debug = logger.isEnabledFor(logging.DEBUG)
        self.logger = logger

        try:
            self.tap = TunTapDevice(self.config.private_interface,
                                    flags=(IFF_TAP | IFF_NO_PI))
        except TunError as e:
            code = ''
            msg = e.args
            if len(e.args) == 2:
                code, msg = e.args
            self.logger.error(f'Error opening device: {code} {msg}')
            if code == 2:
                self.logger.error(
                    'You need to run as root or with sudo to open the TAP interface'
                )
                self.logger.error(
                    f'If you are using docker, add --privileged flag')
            self.logger.error(f'Exiting...')
            exit(1)

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
                lease_time=self.config.dhcp_lease_time,
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

    def _on_send_done(self, future: Future) -> None:
        if future.exception():
            self.logger.warning(
                f'Error sending message to client: {future.exception()}')

    def broadcast(self) -> None:
        message = self.tap.read(1024 * 4)
        dst_mac = format_mac(message[:6])
        for connection in self._connections:
            try:
                if self.is_debug:
                    self.logger.debug(
                        f'Sending to {dst_mac} | connection: {connection.mac} | hwaddr: {self.hw_addr}'
                    )

                if dst_mac in [self.broadcast_addr, connection.mac]:
                    create_task(connection.websocket.send(message),
                                name='broadcast').add_done_callback(
                                    partial(self._on_send_done))
                    continue

                if dst_mac.startswith(self.whitelist_macs):
                    create_task(connection.websocket.send(message),
                                name='broadcast').add_done_callback(
                                    partial(self._on_send_done))

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

                mac = format_mac(message[6:12])  # type: ignore
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
        self.ws_server = await websockets_serve(self.websocket_handler,
                                                self.config.host,
                                                self.config.port,
                                                ssl=self.config.ssl)
        self.logger.info(
            f'Service running on {self.config.host}:{self.config.port}')
        if self.config.public_interface:
            await self.netfilter_svc.start()
        if self.config.enable_dhcp:
            await self.dhcp_svc.start()
        self._waiter_ = self.loop.create_future()

    async def _blocking(self) -> None:
        await self.start()
        return await asyncio.shield(self._waiter_)

    async def stop(self) -> None:

        self.logger.info('Stopping service...')
        self.ws_server.close()

        if self.config.enable_dhcp:
            await self.dhcp_svc.stop()
        if self.config.public_interface:
            await self.netfilter_svc.stop()

        await self.ws_server.wait_closed()
        self.loop.remove_reader(self.tap.fileno())
        self.tap.close()
        self._waiter_.set_result(None)

    async def __aenter__(self) -> 'Server':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()

    def __await__(self) -> Generator[Any, None, None]:
        return self._blocking().__await__()
