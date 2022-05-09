import asyncio
import logging
import os
import ssl
import sys

import uvloop

from tapws import Server, create_tap_device


async def main():
    virtual_ethernet = create_tap_device()
    virtual_ethernet.up()

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
    port = os.environ.get('PORT', '8080')

    server = Server(device=virtual_ethernet,
                    host=host,
                    port=port,
                    ssl=ssl_context)
    print('Starting server...')
    await server.start()


if __name__ == '__main__':
    log_level = os.environ.get('LOG_LEVEL', 'ERROR').upper()
    logging.basicConfig(stream=sys.stdout, level=log_level)
    uvloop.install()

    asyncio.run(main(), debug=log_level == 'DEBUG')
