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
    waiter = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, waiter.set_result, None)

    print("Starting service")
    async with Server(ServerConfig.From_env()):
        await waiter
        print("Stopping service")
    print("Service Stopped")


if __name__ == "__main__":
    log_level = os.environ.get("LOG_LEVEL", "ERROR").upper()
    logging.basicConfig(stream=sys.stdout, level=log_level)
    uvloop.install()
    asyncio.run(main(), debug=log_level == "DEBUG")
