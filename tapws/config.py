#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import ssl
from ipaddress import IPv4Address, IPv4Network
from typing import List, Optional


class ServerConfig:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        private_interface: str = "tap0",
        intra_ip: IPv4Address = IPv4Address("10.11.12.254"),
        intra_network: IPv4Network = IPv4Network("10.11.12.0"),
        router_ip: IPv4Address = IPv4Address("10.11.12.254"),
        dns_ips: List[IPv4Address] = [IPv4Address("1.1.1.1")],
        enable_dhcp: bool = False,
        dhcp_lease_time: int = 3600,
        ssl: Optional[ssl.SSLContext] = None,
        public_interface: Optional[str] = None,
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
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", "8080"))

        # Specify the (public) network interface name you want to 'share' with tap devices
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

        return cls(
            host=host,
            port=port,
            private_interface=interface_name,
            public_interface=public_interface,
            intra_ip=interface_ip,
            intra_network=interface_network,
            router_ip=interface_ip,
            enable_dhcp=enable_dhcp,
            dhcp_lease_time=dhcp_lease_time,
            ssl=ssl_context,
            dns_ips=dns_ips,
        )
