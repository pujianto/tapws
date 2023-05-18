#!/usr/bin/env python
# -*- coding: utf-8 -*-

import typing
import asyncio
import logging
from .config import ServerConfig
from ..services.base import BaseService
from .tuntap import TuntapWrapper
from .websocket import WebSocket


class Server(object):
    _waiter_: asyncio.Future[None]

    def __init__(
        self,
        config: ServerConfig,
        *,
        services: typing.List[BaseService] = [],
        websocket_wrapper: typing.Type[WebSocket] = WebSocket,
        tuntap_wrapper: typing.Type[TuntapWrapper] = TuntapWrapper,
        loop: typing.Optional[asyncio.AbstractEventLoop] = None,
        logger: logging.Logger = logging.getLogger("tapws.server")
    ) -> None:
        self.config = config
        self.device = tuntap_wrapper(
            self.config.private_interface,
            str(self.config.intra_ip),
            str(self.config.intra_network.netmask),
            1500,
        )

        self.ws = websocket_wrapper(
            self.device.awrite, self.config.host, self.config.port, ssl=self.config.ssl
        )

        self.services = services
        self.logger = logger
        if not loop:
            loop = asyncio.get_running_loop()
        self.loop = loop

    async def start(self) -> None:
        self.logger.info("Starting service...")

        self.loop.add_reader(self.device.fileno(), self.ws.broadcast)
        await self.device.start()
        await self.ws.start()
        for service in self.services:
            await service.start()

        self._waiter_ = self.loop.create_future()

    async def stop(self) -> None:
        self.logger.info("Stopping service...")

        self.loop.remove_reader(self.device.fileno())
        for service in self.services:
            await service.stop()

        await self.ws.stop()
        await self.device.stop()
        self._waiter_.set_result(None)

    async def __aenter__(self) -> "Server":
        await self.start()
        return self

    async def __aexit__(self, *args) -> None:
        await self.stop()

    async def _blocking(self) -> None:
        await self.start()
        return await asyncio.shield(self._waiter_)

    def __await__(self) -> typing.Generator[typing.Any, None, None]:
        return self._blocking().__await__()
