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
            int(self.config.server_router),
            int(self.config.server_network.network_address),
            int(self.config.server_network.broadcast_address),
        ]

        self.leases_cleanup_timer = 60

        logger = logging.getLogger('tapws.dhcp')
        self.is_debug = logger.isEnabledFor(logging.DEBUG)
        self.logger = logger

    def get_usable_ip(self, excludes: List[IPv4Address] = []) -> IPv4Address:
        leased_ips = [int(lease.ip) for lease in self._dhcp_leases]
        if self.is_debug:
            self.logger.debug(f'leased ips: {leased_ips}')

        excludes_int = [int(ip) for ip in excludes]
        for ip in self.config.server_network.hosts():

            if self.is_debug:
                self.logger.debug(f'Checking IP {IPv4Address(ip)}')
            if int(ip) in excludes_int:
                continue
            if int(ip) in self.reserved_ips:
                continue
            if int(ip) not in leased_ips:
                return ip
        raise IPv4UnavailableError(f'DHCP server is full')

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

    def get_lease_by_mac(self, mac: bytes) -> Optional[Lease]:
        for lease in self._dhcp_leases:
            if lease.mac == mac:
                return lease
        return None

    def renew_lease(self, lease: Lease) -> None:
        lease.renew(self.config.lease_time_second)
        self._dhcp_leases.add(lease)
        self.logger.info(f'lease {lease} renewed')

    def remove_lease(self, lease: Lease) -> None:
        self._dhcp_leases.remove(lease)
        self.logger.info(f'lease {lease} removed')

    async def restart(self) -> None:
        self.logger.info('restarting DHCP service')
        await self.stop()
        await self.start()
        self.logger.info('DHCP service restarted')

    def create_lease(self,
                     mac: bytes,
                     ip: Optional[IPv4Address] = None) -> Lease:

        ip = ip or self.get_usable_ip()
        return Lease(mac, int(ip), self.config.lease_time_second)

    async def start(self) -> None:

        factory = partial(DHCPServerProtocol, self)
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(
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
        self.logger.info(
            f'DHCP Lease time: {self.config.lease_time_second} seconds')

        self.cleanup_task = asyncio.create_task(self.cleanup_leases())

    async def cleanup_leases(self) -> None:
        while True:
            await asyncio.sleep(self.leases_cleanup_timer)
            if self.is_debug:
                self.logger.debug('Cleaning up leases')
            for lease in list(self._dhcp_leases):
                if lease.expired:
                    self.logger.info(f'Removing expired lease {lease}')
                    self.remove_lease(lease)

    async def stop(self) -> None:
        self.logger.info('Stopping DHCP service')
        self.cleanup_task.cancel()
        self.transport.close()
        self.logger.info('DHCP service stopped')
