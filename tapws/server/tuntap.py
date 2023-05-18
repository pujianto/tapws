#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import typing
from pytun import TunTapDevice, IFF_TAP, IFF_NO_PI, Error as TunError


class TuntapWrapper(object):
    is_up: bool

    def __init__(
        self,
        interface: str,
        address: str,
        netmask: str,
        mtu: int,
        *,
        flags: int = (IFF_TAP | IFF_NO_PI),
        device_cls: typing.Type[TunTapDevice] = TunTapDevice,
        logger: logging.Logger = logging.getLogger("tapws.tuntapwrapper"),
    ) -> None:
        self.is_up = False
        self.logger = logger
        try:
            self.device = device_cls(interface, flags=flags)
            self.device.addr = address
            self.device.netmask = netmask
            self.device.mtu = mtu
        except TunError as e:
            code = 0
            msg = e.args
            if len(e.args) == 2:
                code, msg = e.args
            self.logger.error(f"Error opening device: {code} {msg}")
            if code == 2:
                self.logger.error(
                    "You need to run as root or with sudo to open the TAP interface"
                )
                self.logger.error(f"If you are using docker, add --privileged flag")
            raise e

    def fileno(self) -> int:
        return self.device.fileno()

    async def awrite(self, message: bytes) -> None:
        self.write(message)

    async def start(self) -> None:
        if not self.is_up:
            self.device.up()
            self.is_up = True

    async def stop(self) -> None:
        if self.is_up:
            self.device.close()
            self.is_up = False

    def read(self) -> bytes:
        return self.device.read(1024 * 4)

    def write(self, message: bytes) -> None:
        try:
            self.device.write(message)
        except TunError as e:
            self.logger.error(f"Error writing to device: {e}")
