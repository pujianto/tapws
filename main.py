#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import signal
import sys

import uvloop

from tapws import Server
from tapws.config import ServerConfig
from tapws.services import DHCPConfig
from tapws.services import DHCPServer
from tapws.services import Netfilter
from tapws.services.dhcp.database import Database


async def main():  # pragma: no cover
    loop = asyncio.get_running_loop()
    waiter = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, waiter.set_result, None)

    print("Starting service")

    server_config = ServerConfig.From_env()
    services = []

    if server_config.enable_dhcp:
        dhcp_config = DHCPConfig(
            server_ip=server_config.intra_ip,
            server_network=server_config.intra_network,
            server_router=server_config.router_ip,
            dns_ips=server_config.dns_ips,
            lease_time=server_config.dhcp_lease_time,
            bind_interface=server_config.private_interface,
        )

        client_database = Database(dhcp_config.lease_time)
        dhcp_service = DHCPServer(dhcp_config, client_database)
        services.append(dhcp_service)

    if server_config.public_interface:
        netfilter_service = Netfilter(
            public_interface=server_config.public_interface,
            private_interface=server_config.private_interface,
        )
        services.append(netfilter_service)

    server = Server(server_config, services)

    async with server:
        await waiter
        print("Stopping service")
    print("Service Stopped")


if __name__ == "__main__":
    log_level = os.environ.get("LOG_LEVEL", "ERROR").upper()
    logging.basicConfig(stream=sys.stdout, level=log_level)
    uvloop.install()
    asyncio.run(main(), debug=log_level == "DEBUG")
