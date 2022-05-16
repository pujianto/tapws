#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import socket
from functools import partial
from ipaddress import IPv4Address, IPv4Network
from typing import Optional

from ..base import BaseService
from .protocol import DHCPServerProtocol
from .utils import IPv4UnavailableError, Lease


class DHCPServer(BaseService):

    _dhcp_leases = set()

    def __init__(self, ip_address: IPv4Address, ip_network: IPv4Network,
                 bind_interface: str) -> None:
        self.ip_network = ip_network
        self.ip = ip_address
        self.port = 67
        self.loop = asyncio.get_running_loop()
        self.tap_name = bind_interface

        self.lease_time_second = 3600
        self.dns_ips = [IPv4Address('1.1.1.1'), IPv4Address('8.8.8.8')]
        self.reserved_ips = [int(self.ip)]

    def get_usable_ip(self) -> Optional[IPv4Address]:
        ip_start = int(self.ip_network.network_address + 1)
        ip_end = int(self.ip_network.broadcast_address - 1)

        for ip in range(ip_start, ip_end):
            logging.debug(f'Checking IP {IPv4Address(ip)}')
            if ip in self.reserved_ips:
                continue
            if len(self._dhcp_leases) < 1:
                return IPv4Address(ip)
            for lease in self._dhcp_leases:
                if ip != int(lease.ip):
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
        logging.debug(f'Added lease {lease}')

    def remove_lease(self, lease: Lease) -> None:
        self._dhcp_leases.remove(lease)
        logging.debug(f'Removed lease {lease}')

    def create_lease(self,
                     mac: str,
                     ip: Optional[IPv4Address] = None) -> Optional[Lease]:
        ip = ip or self.get_usable_ip()
        if ip is None:
            raise IPv4UnavailableError
        return Lease(mac, int(ip), self.lease_time_second)

    async def start(self) -> None:

        logging.info('Starting DHCP service')
        factory = partial(DHCPServerProtocol, self)
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(
            lambda: factory(),
            local_addr=('0.0.0.0', self.port),
            allow_broadcast=True)

        self.transport.get_extra_info('socket').setsockopt(
            socket.SOL_SOCKET, 25, bytes(self.tap_name, 'utf-8'))

        name = '%s:%d' % self.transport.get_extra_info('socket').getsockname()
        logging.info(f'DHCP listening on {name}')

    async def stop(self) -> None:
        self.transport.close()
