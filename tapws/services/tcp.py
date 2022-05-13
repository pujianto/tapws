import asyncio
from functools import partial

from .base import BaseService


class EchoServerProtocol(asyncio.Protocol):

    def connection_made(self, transport):
        peername = transport.get_extra_info('peername')
        print('Connection from {}'.format(peername))
        self.transport = transport

    def data_received(self, data):
        message = data.decode()
        print('Data received: {!r}'.format(message))

        print('Send: {!r}'.format(message))
        self.transport.write(data)

        print('Close the client socket')
        self.transport.close()


class EchoServer(BaseService):

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.loop = asyncio.get_running_loop()
        asyncio.create_task(self._ainit())

    async def _ainit(self):
        print('Serving on {}'.format(self.host))
        loop = asyncio.get_running_loop()
        factory = partial(EchoServerProtocol)
        self.server = await loop.create_server(lambda: factory(), self.host, self.port)

    def close(self):
        self.server.close()
