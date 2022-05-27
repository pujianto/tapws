#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
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

    @classmethod
    def From_env(cls) -> "DHCPConfig":
        interface_ip = IPv4Address(os.environ.get("INTERFACE_IP", "10.11.12.254"))
        interface_subnet = int(os.environ.get("INTERFACE_SUBNET", "24"))
        if interface_subnet > 31 or interface_subnet < 0:
            raise ValueError(
                "INTERFACE_SUBNET must be between 0 and 31, defaults set to 24"
            )
        interface_network = IPv4Network(
            f"{interface_ip}/{interface_subnet}", strict=False
        )
        interface_name = "tapx"
        dhcp_lease_time = int(os.environ.get("DHCP_LEASE_TIME", "3600"))
        if dhcp_lease_time < -1:
            raise ValueError("DHCP_LEASE_TIME must be -1 or greater")
        dns_ips = [IPv4Address("1.1.1.1"), IPv4Address("8.8.8.8")]

        return cls(
            server_ip=interface_ip,
            server_network=interface_network,
            server_router=interface_ip,
            bind_interface=interface_name,
            lease_time=dhcp_lease_time,
            dns_ips=dns_ips,
        )

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
