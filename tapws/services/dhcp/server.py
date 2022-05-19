#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import socket
from functools import partial
from ipaddress import IPv4Address
from typing import Optional

from tapws.services.dhcp.config import DHCPConfig

from ..base import BaseService
from .lease import Lease
from .packet import IPv4UnavailableError
from .protocol import DHCPServerProtocol


class DHCPServer(BaseService):

    def __init__(self, config: DHCPConfig) -> None:

        self._dhcp_leases = set()

        self.config = config
        self.loop = asyncio.get_running_loop()
        self.reserved_ips = [
            int(self.config.server_ip),
            int(self.config.server_router)
        ]

        logger = logging.getLogger('tapws.dhcp')
        self.is_debug = logger.isEnabledFor(logging.DEBUG)
        self.logger = logger

    def get_usable_ip(self) -> Optional[IPv4Address]:
        ip_start = int(self.config.server_network.network_address + 1)
        ip_end = int(self.config.server_network.broadcast_address - 1)

        leased_ips = [int(lease.ip) for lease in self._dhcp_leases]

        for ip in range(ip_start, ip_end):
            if self.is_debug:
                self.logger.debug(f'Checking IP {IPv4Address(ip)}')

            if ip in self.reserved_ips:
                continue
            if ip not in leased_ips:
                return IPv4Address(ip)

        return None

    def is_ip_available(self, ip: IPv4Address) -> bool:
        if int(ip) in self.reserved_ips:
            return False

        if len(self._dhcp_leases) < 1:
            return True

        for lease in self._dhcp_leases:
            if int(ip) == int(lease.ip):
                return False

        return True

    def add_lease(self, lease: Lease) -> None:
        self._dhcp_leases.add(lease)
        self.logger.info(f'new lease added: {lease}')

    def remove_lease(self, lease: Lease) -> None:
        self._dhcp_leases.remove(lease)
        self.logger.info(f'lease {lease} removed')

    async def restart(self) -> None:
        self.logger.info('restarting DHCP service')
        await self.stop()
        await self.start()
        self.logger.info('DHCP service restarted')

    def create_lease(self,
                     mac: str,
                     ip: Optional[IPv4Address] = None) -> Lease:
        ip = ip or self.get_usable_ip()
        if ip is None:
            raise IPv4UnavailableError
        return Lease(mac, int(ip), self.config.lease_time_second)

    async def start(self) -> None:

        self.logger.info('Starting DHCP service')
        factory = partial(DHCPServerProtocol, self)
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(
            lambda: factory(),
            local_addr=('0.0.0.0', 67),
            allow_broadcast=True)
        self.cleanup_task = asyncio.create_task(self.cleanup_leases())
        self.transport.get_extra_info('socket').setsockopt(
            socket.SOL_SOCKET, 25, bytes(self.config.bind_interface, 'utf-8'))

        name = '%s:%d' % self.transport.get_extra_info('socket').getsockname()
        self.logger.info(f'DHCP listening on {name}')

    async def cleanup_leases(self) -> None:
        while True:
            if self.is_debug:
                self.logger.debug('Cleaning up leases')
            for lease in list(self._dhcp_leases):
                if lease.expired:
                    self.logger.info(f'Removing expired lease {lease}')
                    self.remove_lease(lease)

            await asyncio.sleep(60)

    async def stop(self) -> None:
        self.logger.info('Stopping DHCP service')
        self.cleanup_task.cancel()
        self.transport.close()
        self.logger.info('DHCP service stopped')
