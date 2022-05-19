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


async def main():
    loop = asyncio.get_running_loop()

    server_config = ServerConfig.From_env()
    server = Server(server_config)

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
