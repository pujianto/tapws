import asyncio
import logging
import os
import sys

import uvloop

from tapws import Server, create_tap_device


async def main():
    virtual_ethernet = create_tap_device()
    virtual_ethernet.up()
    server = Server(device=virtual_ethernet)

    await server.start()


if __name__ == '__main__':
    log_level = os.environ.get('LOG_LEVEL', 'ERROR').upper()
    logging.basicConfig(stream=sys.stdout, level=log_level)
    uvloop.install()

    asyncio.run(main(), debug=log_level == 'DEBUG')
