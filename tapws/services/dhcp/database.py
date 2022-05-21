#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Generator, List, Optional

from ...utils import format_mac
from .lease import Lease


class Database:

    __slots__ = ('leases', 'lease_time')

    def __init__(self, lease_time: int, *, leases: List[Lease] = []) -> None:
        self.lease_time = lease_time
        self.leases: List[Lease] = leases

    def get_lease(self, mac: bytes) -> Optional[Lease]:
        for lease in self.leases:
            if lease.mac == mac:
                return lease
        raise ValueError(f'lease not found for mac {format_mac(mac)}')

    def expired_leases(self) -> Generator[Lease, None, None]:
        for lease in self.leases:
            if lease.expired:
                yield lease

    def is_ip_available(self, ip: int) -> bool:
        return ip not in [lease.ip for lease in self.leases]

    def get_leases(self) -> List[Lease]:
        return self.leases

    def add_lease(self, lease: Lease) -> None:
        self.leases.append(lease)

    def remove_lease(self, lease: Lease) -> None:
        self.leases.remove(lease)

    def renew_lease(self, lease: Lease) -> None:
        existing_lease = self.get_lease(lease.mac)
        if existing_lease is not None:
            existing_lease.renew(self.lease_time)
