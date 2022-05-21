#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import socket
from functools import partial
from ipaddress import IPv4Address
from typing import List, Optional

from ..base import BaseService
from .config import DHCPConfig
from .database import Database
from .lease import Lease
from .packet import IPv4UnavailableError
from .protocol import DHCPServerProtocol


class DHCPServer(BaseService):

    __slots__ = (
        'config',
        'loop',
        'cleanup_timer',
        'reserved_ips',
        'is_debug',
        'logger',
        'transport',
        'cleanup_task',
        'database',
    )

    def __init__(self, config: DHCPConfig) -> None:

        self.config = config
        self.database = Database(self.config.lease_time)

        self.loop = asyncio.get_running_loop()
        self.reserved_ips = (
            int(self.config.server_ip),
            int(self.config.server_router),
            int(self.config.server_network.network_address),
            int(self.config.server_network.broadcast_address),
            *[int(ip) for ip in self.config.dns_ips],
        )

        self.cleanup_timer = 60

        logger = logging.getLogger('tapws.dhcp')
        self.is_debug = logger.isEnabledFor(logging.DEBUG)
        self.logger = logger

    async def get_available_ip(self) -> IPv4Address:
        for ip in self.config.server_network.hosts():
            ip_int = int(ip)

            if ip_int in self.reserved_ips:
                continue
            if self.database.is_ip_available(ip_int):
                return ip

        raise IPv4UnavailableError('DHCP server is full')

    async def is_ip_available(self,
                              ip: IPv4Address,
                              mac: Optional[bytes] = None) -> bool:
        if int(ip) in self.reserved_ips:
            return False
        if mac is not None:
            lease = self.database.get_lease(mac)
            if lease is not None and lease.ip == ip:
                return True
        return self.database.is_ip_available(int(ip))

    async def add_lease(self, lease: Lease) -> None:
        self.database.add_lease(lease)
        self.logger.info(f'leasing {lease}')

    async def get_lease_by_mac(self, mac: bytes) -> Optional[Lease]:
        return self.database.get_lease(mac)

    async def renew_lease(self, lease: Lease) -> None:
        self.database.renew_lease(lease)
        self.logger.info(f'{lease} renewed')

    async def remove_lease(self, lease: Lease) -> None:
        self.database.remove_lease(lease)
        self.logger.info(f'{lease} removed')

    async def restart(self) -> None:
        self.logger.info('restarting DHCP service')
        await self.stop()
        await self.start()
        self.logger.info('DHCP service restarted')

    async def start(self) -> None:

        factory = partial(DHCPServerProtocol, self)
        self.transport, _ = await self.loop.create_datagram_endpoint(
            lambda: factory(),
            local_addr=('0.0.0.0', 67),
            allow_broadcast=True)

        self.transport.get_extra_info('socket').setsockopt(
            socket.SOL_SOCKET, 25, bytes(self.config.bind_interface, 'utf-8'))

        name = '%s:%d' % self.transport.get_extra_info('socket').getsockname()
        self.logger.info('Starting DHCP service')
        self.logger.info(
            f'DHCP listening on {name}. interface: {self.config.bind_interface}'
        )
        self.logger.info(f'Router (Gateway): {self.config.server_router}')
        self.logger.info(f'Subnet: {self.config.server_network.netmask}')
        self.logger.info(
            f'Max clients: {self.config.server_network.num_addresses - 3}')
        self.logger.info(
            f'DNS: {",".join([str(dns) for dns in self.config.dns_ips])}')
        lease_time = str(
            self.config.lease_time
        ) + ' seconds' if self.config.lease_time >= 0 else 'infinite'
        self.logger.info(f'Lease time: {lease_time}')

        self.cleanup_task = asyncio.create_task(self.cleanup_leases())

    async def cleanup_leases(self) -> None:
        while True:
            await asyncio.sleep(self.cleanup_timer)
            if self.is_debug:
                self.logger.debug('Cleaning up expired leases')
            async for lease in self.database.expired_leases():
                self.database.remove_lease(lease)

    async def stop(self) -> None:
        self.logger.info('Stopping DHCP service')
        self.cleanup_task.cancel()
        self.transport.close()
        self.logger.info('DHCP service stopped')
