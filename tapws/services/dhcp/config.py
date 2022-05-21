#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ipaddress import IPv4Address, IPv4Network
from typing import List


class DHCPConfig:

    def __init__(
        self,
        server_ip: IPv4Address,
        server_network: IPv4Network,
        server_router: IPv4Address,
        bind_interface: str,
        lease_time: int = 3600,
        dns_ips: List[IPv4Address] = [IPv4Address('1.1.1.1')],
    ) -> None:
        self.server_ip = server_ip
        self.server_network = server_network
        self.server_router = server_router
        self.dns_ips = dns_ips
        self.bind_interface = bind_interface
        self.lease_time = lease_time
