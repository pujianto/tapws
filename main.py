import asyncio
import logging
import os
import signal
import sys

import uvloop
from pytun import IFF_NO_PI, IFF_TAP, TunTapDevice

from tapws.config import ServerConfig
from tapws.server import Server
from tapws.services.dhcp.config import DHCPConfig


async def main():
    loop = asyncio.get_running_loop()
    waiter = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, waiter.set_result, None)

    server_config = ServerConfig.From_env()
    dhcp_config = DHCPConfig(
        server_ip=server_config.intra_ip,
        server_network=server_config.intra_network,
        dns_ips=server_config.dns_ips,
        lease_time=server_config.dhcp_lease_time,
        bind_interface=server_config.private_interface,
        server_router=server_config.router_ip,
    )
    tap = TunTapDevice(server_config.private_interface,
                       flags=(IFF_TAP | IFF_NO_PI))
    tap.addr = str(server_config.intra_ip)
    tap.netmask = str(server_config.intra_network.netmask)
    tap.mtu = 1500
    tap.up()
    print('Starting service')
    async with Server(ServerConfig.From_env(),
                      device=tap,
                      dhcp_config=dhcp_config):
        await waiter
        print('Stopping service')
    print('Service Stopped')
    tap.close()


if __name__ == '__main__':
    log_level = os.environ.get('LOG_LEVEL', 'ERROR').upper()
    logging.basicConfig(stream=sys.stdout, level=log_level)
    uvloop.install()
    asyncio.run(main(), debug=log_level == 'DEBUG')
