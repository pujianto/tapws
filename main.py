import asyncio
import logging
import os
import sys

import uvloop

from tapws.server import Server

if __name__ == '__main__':
    log_level = os.environ.get('LOG_LEVEL', 'ERROR').upper()
    logging.basicConfig(stream=sys.stdout, level=log_level)
    uvloop.install()
    server = Server()
    try:
        asyncio.run(server.start(), debug=log_level == 'DEBUG')
    except KeyboardInterrupt:
        pass
