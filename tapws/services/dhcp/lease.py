#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from ipaddress import IPv4Address


class Lease:

    def __init__(
        self,
        mac: str,
        ip: int,
        lease_time_second: int,
        leased_at: datetime = datetime.now()) -> None:
        self.mac = mac
        self.ip = ip
        self.leased_at = leased_at
        self.lease_time = lease_time_second

    def __hash__(self) -> int:
        return hash(self.ip)

    @property
    def expired(self) -> bool:
        return self.leased_at + timedelta(
            seconds=self.lease_time) < datetime.now()

    def __repr__(self) -> str:
        return f'Lease({self.mac}, {IPv4Address(self.ip)}, {self.lease_time})'