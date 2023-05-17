#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from typing import AsyncGenerator, List, Optional

from .lease import Lease


class Database:
    __slots__ = ("leases", "lease_time", "logger", "is_debug")

    def __init__(self, lease_time: int, *, leases: List[Lease] = []) -> None:
        self.logger = logging.getLogger("tapws.dhcp.database")
        self.is_debug = self.logger.isEnabledFor(logging.DEBUG)
        self.lease_time = lease_time
        self.leases: List[Lease] = leases

    def get_lease(self, mac: bytes) -> Optional[Lease]:
        for lease in self.leases:
            if lease.mac == mac:
                return lease
        return None

    async def expired_leases(self) -> AsyncGenerator[Lease, None]:
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
        if lease not in self.leases:
            self.logger.warning(f"Lease {lease} not found in database")
            return
        if self.is_debug:
            self.logger.debug(f"Removing lease {lease} from database")
        self.leases.remove(lease)

    def renew_lease(self, lease: Lease) -> None:
        existing_lease = self.get_lease(lease.mac)
        if existing_lease is None:
            self.logger.warning(f"Lease {lease} not found in database")
            return
        existing_lease.renew(self.lease_time)
