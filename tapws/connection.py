#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional

from websockets.legacy.server import WebSocketServerProtocol


class Connection:
    __slots__ = ("_mac", "websocket")

    def __init__(
        self, websocket: WebSocketServerProtocol, mac: Optional[str] = None
    ) -> None:
        self._mac = mac
        self.websocket = websocket

    def __repr__(self) -> str:
        return f"Connection({self.websocket})"

    @property
    def mac(self) -> Optional[str]:
        return self._mac

    @mac.setter
    def mac(self, mac) -> None:
        self._mac = mac
