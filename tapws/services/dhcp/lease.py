#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from ipaddress import IPv4Address

from ...utils import format_mac


class Lease:

    __slots__ = ('mac', 'ip', 'lease_time', 'leased_at')

    def __init__(
        self,
        mac: bytes,
        ip: int,
        lease_time: int,
        leased_at: datetime = datetime.now()) -> None:
        self.mac = mac
        self.ip = ip
        self.leased_at = leased_at
        self.lease_time = lease_time

    def __hash__(self) -> int:
        return hash((self.ip, self.mac))

    @property
    def expired(self) -> bool:
        if self.lease_time == -1:
            return False
        return self.leased_at + timedelta(
            seconds=self.lease_time) < datetime.now()

    def renew(self, lease_time: int) -> None:
        self.leased_at = datetime.now()
        self.lease_time = lease_time

    def __repr__(self) -> str:

        return f'Lease({format_mac(self.mac)}, {IPv4Address(self.ip)}, {self.lease_time})'
