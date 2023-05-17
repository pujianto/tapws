#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ipaddress import IPv4Address, IPv4Network
from typing import List


class DHCPConfig:
    __slots__ = (
        "server_ip",
        "server_router",
        "server_network",
        "bind_interface",
        "lease_time",
        "dns_ips",
    )

    def __init__(
        self,
        server_ip: IPv4Address,
        server_network: IPv4Network,
        server_router: IPv4Address,
        bind_interface: str,
        lease_time: int = 3600,
        dns_ips: List[IPv4Address] = [IPv4Address("1.1.1.1")],
    ) -> None:
        self.server_ip = server_ip
        self.server_network = server_network
        self.server_router = server_router
        self.dns_ips = dns_ips
        self.bind_interface = bind_interface
        self.lease_time = lease_time

    @property
    def netmask_ip(self) -> IPv4Address:
        return self.server_network.netmask

    def dhcp_opts(self) -> dict:
        return {
            "server_ip": self.server_ip,
            "server_router": self.server_router,
            "netmask_ip": self.netmask_ip,
            "dns_ips": self.dns_ips,
            "lease_time": self.lease_time,
        }
