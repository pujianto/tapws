#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import signal
import ssl
import sys
from ipaddress import IPv4Address, IPv4Network

import uvloop

from tapws import Server
from tapws.services import DHCPServer


async def main():
    ssl_context = None
    if os.environ.get('WITH_SSL', 'False').lower() in ('true', '1', 'yes'):
        fullchain_cert_path = os.environ.get('SSL_CERT_PATH',
                                             '/app/certs/fullchain.pem')
        key_path = os.environ.get('SSL_KEY_PATH', '/app/certs/privkey.pem')
        passphrase = os.environ.get('SSL_PASSPHRASE', None)
        if not fullchain_cert_path or not key_path:
            raise ValueError(
                'SSL_CERT_PATH and SSL_KEY_PATH must be set if WITH_SSL is set to True'
            )
        if not os.path.isfile(fullchain_cert_path) or not os.path.isfile(
                key_path):
            raise ValueError(
                'SSL_CERT_PATH and SSL_KEY_PATH must be set to valid paths if WITH_SSL is set to True'
            )
        ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(fullchain_cert_path,
                                    keyfile=key_path,
                                    password=passphrase)
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', '8080'))

    interface_ip = IPv4Address(os.environ.get('INTERFACE_IP', '10.11.12.1'))
    interface_name = 'tapx'
    interface_subnet = 24
    interface_network = IPv4Network(f'{interface_ip}/{interface_subnet}',
                                    strict=False)

    services = []

    # DHCP server
    if os.environ.get('WITH_DHCP', 'True').lower() in ('true', '1', 'yes'):
        dhcp_server = DHCPServer(interface_ip, interface_network,
                                 interface_name)
        services.append(dhcp_server)

    # Main server
    server = Server(host=host,
                    port=port,
                    ssl=ssl_context,
                    interface_ip=interface_ip,
                    interface_name=interface_name,
                    interface_subnet=interface_subnet,
                    services=services)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig,
                                lambda: asyncio.create_task(server.stop()))

    print('Starting service')
    await server.start()


if __name__ == '__main__':
    log_level = os.environ.get('LOG_LEVEL', 'ERROR').upper()
    logging.basicConfig(stream=sys.stdout, level=log_level)
    uvloop.install()
    asyncio.run(main(), debug=log_level == 'DEBUG')
