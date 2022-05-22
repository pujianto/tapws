import asyncio
from functools import partial
from typing import Optional

from aiohttp import web
from aiohttp.http_websocket import WSCloseCode
from aiohttp.web import Application
from pytun import TunTapDevice

from .config import ServerConfig
from .services.dhcp.config import DHCPConfig
from .services.dhcp.server import DHCPServer
from .services.netfilter.netfilter import Netfilter
from .wshandler import WebsocketHandler


class Server:

    def __init__(self,
                 config: ServerConfig,
                 device: TunTapDevice,
                 *,
                 dhcp_config: Optional[DHCPConfig] = None):
        self.loop = asyncio.get_running_loop()
        self.config = config
        self.dhcp_config = dhcp_config
        self.device = device
        self.ws_handler = WebsocketHandler(device)
        self.app = Application()
        self.app.add_routes(self.ws_handler.routes)

        if self.dhcp_config:
            self.dhcp_svc = DHCPServer(self.dhcp_config)
        if self.config.public_interface:
            self.netfilter_svc = Netfilter(
                public_interface=self.config.public_interface,
                private_interface=self.config.private_interface)

    async def _on_shutdown(self, app: Application) -> None:
        for connection in self.ws_handler.connections:
            await connection.websocket.close(code=WSCloseCode.GOING_AWAY,
                                             message=b'Server shutdown')

    async def start(self):
        self.runner = web.AppRunner(self.app)
        self.app.on_shutdown.append(self._on_shutdown)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner,
                                self.config.host,
                                self.config.port,
                                ssl_context=self.config.ssl)
        self.loop.add_reader(self.device.fileno(),
                             partial(self.ws_handler.broadcast))
        await self.site.start()
        if self.config.enable_dhcp:
            await self.dhcp_svc.start()
        if self.config.public_interface:
            await self.netfilter_svc.start()
        self._waiter_ = self.loop.create_future()

    async def stop(self):
        if self.config.enable_dhcp:
            await self.dhcp_svc.stop()
        if self.config.public_interface:
            await self.netfilter_svc.stop()
        await self.site.stop()
        await self.runner.cleanup()

    async def __aenter__(self) -> 'Server':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def _blocking(self):
        await self.start()
        return await asyncio.shield(self._waiter_)

    def __repr__(self):
        return f'<Serv {self.config}>'

    def __await__(self):
        return self._blocking().__await__()
