#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import signal
import sys

import uvloop

from tapws.server import Server, ServerConfig
from tapws.services import DHCPConfig, DHCPServer, Netfilter
from tapws.services.dhcp.database import Database
from tapws.utils import on_done
from functools import partial


async def main():  # pragma: no cover
    loop = asyncio.get_running_loop()
    waiter = loop.create_future()
    logger = logging.getLogger("tapws.__main__")
    waiter.add_done_callback(partial(on_done, logger))
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

    try:
        server = Server(server_config, services=services)

        async with server:
            await waiter
            print("Stopping service")
        print("Service Stopped")
    except Exception as e:
        print(f"An error occurred. {e}")
        exit(1)


if __name__ == "__main__":
    log_level = os.environ.get("LOG_LEVEL", "ERROR").upper()
    logging.basicConfig(stream=sys.stdout, level=log_level)
    uvloop.install()
    asyncio.run(main(), debug=log_level == "DEBUG")
