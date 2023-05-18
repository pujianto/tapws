#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import ssl
from ipaddress import IPv4Address, IPv4Network, AddressValueError
from typing import List, Optional


class ServerConfig:
    def __init__(
        self,
        host: str,
        port: int,
        private_interface: str,
        intra_ip: IPv4Address,
        intra_network: IPv4Network,
        router_ip: IPv4Address,
        dns_ips: List[IPv4Address],
        enable_dhcp: bool,
        dhcp_lease_time: int,
        *,
        public_interface: Optional[str] = None,
        ssl: Optional[ssl.SSLContext] = None,
    ):
        self.host = host
        self.port = port
        self.private_interface = private_interface
        self.public_interface = public_interface
        self.intra_ip = intra_ip
        self.intra_network = intra_network
        self.router_ip = router_ip
        self.dns_ips = dns_ips
        self.ssl = ssl
        self.dhcp_lease_time = dhcp_lease_time
        self.enable_dhcp = enable_dhcp

    def __repr__(self) -> str:
        return f"ServerConfig(ip={self.host}, port={self.port}...)"

    @classmethod
    def From_env(cls) -> "ServerConfig":
        ssl_context = None
        if os.environ.get("WITH_SSL", "False").lower() in ("true", "1", "yes"):
            fullchain_cert_path = os.environ.get(
                "SSL_CERT_PATH", "/app/certs/fullchain.pem"
            )
            key_path = os.environ.get("SSL_KEY_PATH", "/app/certs/privkey.pem")
            passphrase = os.environ.get("SSL_PASSPHRASE", None)
            if not fullchain_cert_path or not key_path:
                raise ValueError(
                    "SSL_CERT_PATH and SSL_KEY_PATH must be set if WITH_SSL is set to True"
                )
            if not os.path.isfile(path=fullchain_cert_path) or not os.path.isfile(
                key_path
            ):
                raise ValueError(
                    "SSL_CERT_PATH and SSL_KEY_PATH must be set to valid paths if WITH_SSL is set to True"
                )
            ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(
                fullchain_cert_path, keyfile=key_path, password=passphrase
            )
        try:
            host = IPv4Address(os.environ.get("HOST", "0.0.0.0")).exploded
        except AddressValueError as e:
            raise ValueError(str(e))

        port = int(os.environ.get("PORT", "8080"))

        # Specify the (public) network interface name you want to 'share' with the tap device
        public_interface = os.environ.get("PUBLIC_INTERFACE", None)
        interface_ip = IPv4Address(os.environ.get("INTERFACE_IP", "10.11.12.254"))
        interface_name = "tapx"
        interface_subnet = int(os.environ.get("INTERFACE_SUBNET", "24"))

        if interface_subnet > 31 or interface_subnet < 0:
            raise ValueError(
                "INTERFACE_SUBNET must be between 0 and 31, defaults set to 24"
            )

        interface_network = IPv4Network(
            f"{interface_ip}/{interface_subnet}", strict=False
        )

        enable_dhcp = os.environ.get("WITH_DHCP", "True").lower() in (
            "true",
            "1",
            "yes",
        )
        dhcp_lease_time = int(os.environ.get("DHCP_LEASE_TIME", "3600"))
        if dhcp_lease_time < -1:
            raise ValueError("DHCP_LEASE_TIME must be -1 or greater")
        dns_ips = [IPv4Address("1.1.1.1"), IPv4Address("8.8.8.8")]

        private_interface = interface_name
        intra_ip = interface_ip
        intra_network = interface_network
        router_ip = interface_ip

        return cls(
            host,
            port,
            private_interface,
            intra_ip,
            intra_network,
            router_ip,
            dns_ips,
            enable_dhcp,
            dhcp_lease_time,
            public_interface=public_interface,
            ssl=ssl_context,
        )
