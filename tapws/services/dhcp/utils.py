#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from ipaddress import IPv4Address
from typing import Optional

from dpkt import dhcp


class IPv4UnavailableError(Exception):
    pass


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


class DHCPPacket:

    @staticmethod
    def unpack(data: bytes) -> dhcp.DHCP:
        packet = dhcp.DHCP()
        packet.unpack(data)
        return packet

    @staticmethod
    def request_type(packet: dhcp.DHCP) -> Optional[str]:
        if packet.op != dhcp.DHCP_OP_REQUEST:
            return None
        request_type = {
            1: 'discover',
            3: 'request',
        }
        for op in packet.opts:
            opt_key, opt_value = op
            if opt_key == dhcp.DHCP_OPT_MSGTYPE:
                return request_type.get(ord(opt_value), None)

    @staticmethod
    def seconds_to_bytes(seconds: int) -> bytes:
        return bytes(hex(seconds), 'ascii')

    @staticmethod
    def get_requested_ip(packet: dhcp.DHCP) -> Optional[IPv4Address]:
        for opt in packet.opts:
            opt_key, opt_value = opt
            if opt_key == dhcp.DHCP_OPT_REQ_IP:
                return IPv4Address(opt_value)
        return None
