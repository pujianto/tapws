#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ipaddress import IPv4Address
import typing

from dpkt import dhcp


class DHCPPacket(dhcp.DHCP):
    opts: typing.List[typing.Tuple]
    secs: int
    xid: int
    ciaddr: int
    chaddr: bytes

    def __init__(self, *args, **kwargs) -> None:
        self.secs = 0
        self.xid = 0
        self.ciaddr = 0
        self.chaddr = b""
        super().__init__(*args, **kwargs)

    def get_option_value(self, option_code: int) -> typing.Optional[str]:
        for option in self.opts:
            opt_key, opt_value = option
            if opt_key == option_code:
                return opt_value
        return None

    @property
    def request_type(self) -> int:
        if self.op != dhcp.DHCP_OP_REQUEST:  # type: ignore
            return -1
        value = self.get_option_value(dhcp.DHCP_OPT_MSGTYPE)
        if value:
            return ord(value)
        return -1

    @staticmethod
    def seconds_to_bytes(seconds: int) -> bytes:
        return seconds.to_bytes(4, byteorder="big", signed=True)

    @classmethod
    def Offer(
        cls,
        ip: IPv4Address,
        server_ip: IPv4Address,
        server_router: IPv4Address,
        netmask_ip: IPv4Address,
        secs: int,
        mac: bytes,
        xid: int,
        lease_time: int = 3600,
        dns_ips: list = ["1.1.1.1"],
    ) -> "DHCPPacket":
        packet = cls(
            chaddr=mac,
            op=dhcp.DHCP_OP_REPLY,
            xid=xid,
            secs=secs,
            yiaddr=int(ip),
            siaddr=int(server_ip),
        )
        message_type = bytes(chr(dhcp.DHCPOFFER), "ascii")

        packet.opts = cls._build_options(
            message_type,
            lease_time=lease_time,
            dns_ips=dns_ips,
            router_ip=server_router,
            netmask=netmask_ip,
        )
        return packet

    @classmethod
    def Ack(
        cls,
        ip: IPv4Address,
        server_ip: IPv4Address,
        server_router: IPv4Address,
        netmask_ip: IPv4Address,
        mac: bytes,
        secs: int,
        xid: int,
        lease_time: int = 3600,
        dns_ips: list = ["1.1.1.1"],
    ) -> "DHCPPacket":
        packet = cls(
            op=dhcp.DHCP_OP_REPLY,
            chaddr=mac,
            xid=xid,
            secs=secs,
            yiaddr=int(ip),
            siaddr=int(server_ip),
        )
        message_type = bytes(chr(dhcp.DHCPACK), "ascii")
        packet.opts = cls._build_options(
            message_type,
            lease_time=lease_time,
            dns_ips=dns_ips,
            router_ip=server_router,
            netmask=netmask_ip,
        )

        return packet

    @classmethod
    def Nak(cls, xid: int, mac: bytes) -> "DHCPPacket":
        packet = cls(
            op=dhcp.DHCP_OP_REPLY,
            chaddr=mac,
            xid=xid,
            opts=[(dhcp.DHCP_OPT_MSGTYPE, bytes(chr(dhcp.DHCPNAK), "ascii"))],
        )

        return packet

    @staticmethod
    def _build_options(
        message_type: bytes,
        lease_time: int,
        dns_ips: typing.List[IPv4Address],
        router_ip: IPv4Address,
        netmask: IPv4Address,
    ) -> typing.List:
        if lease_time != -1:
            renew_time = int(lease_time * 0.5)
            rebind_time = int(lease_time * 0.875)
        else:
            renew_time = rebind_time = -1

        options = [
            (dhcp.DHCP_OPT_MSGTYPE, message_type),
            (dhcp.DHCP_OPT_NETMASK, netmask.packed),
            (dhcp.DHCP_OPT_ROUTER, router_ip.packed),
            (dhcp.DHCP_OPT_RENEWTIME, DHCPPacket.seconds_to_bytes(renew_time)),
            (dhcp.DHCP_OPT_REBINDTIME, DHCPPacket.seconds_to_bytes(rebind_time)),
            (dhcp.DHCP_OPT_LEASE_SEC, DHCPPacket.seconds_to_bytes(lease_time)),
            (dhcp.DHCP_OPT_SERVER_ID, router_ip.packed),
            (dhcp.DHCP_OPT_ROUTER, router_ip.packed),
            (dhcp.DHCP_OPT_DNS_SVRS, b"".join(dns.packed for dns in dns_ips)),
        ]
        return options


class IPv4UnavailableError(Exception):
    pass
