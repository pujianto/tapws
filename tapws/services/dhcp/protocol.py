#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
from asyncio.transports import DatagramTransport
from ipaddress import IPv4Address
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .server import DHCPServer

from .packet import DHCPPacket, IPv4UnavailableError, dhcp


class DHCPServerProtocol(asyncio.DatagramProtocol):

    broadcast_ip = '255.255.255.255'
    broadcast_port = 68

    def __init__(self, server: 'DHCPServer') -> None:
        self._srv = server
        self._response_map = {
            dhcp.DHCPDISCOVER: self.send_offer,
            dhcp.DHCPREQUEST: self.send_ack,
            dhcp.DHCPRELEASE: self.release_lease,
        }
        logger = logging.getLogger('tapws.dhcp')
        self.is_debug = logger.isEnabledFor(logging.DEBUG)
        self.logger = logger

    def broadcast(self, packet: DHCPPacket) -> None:
        if self.is_debug:
            self.logger.debug(f'Broadcasting: {repr(packet)}')
        self.transport.sendto(bytes(packet),
                              (self.broadcast_ip, self.broadcast_port))

    def connection_made(self, transport: DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            packet = DHCPPacket(data)
            if self.is_debug:
                self.logger.debug(f'Incoming packet: {repr(packet)}')

            if packet.request_type:
                self._response_map.get(packet.request_type,
                                       lambda packet: None)(packet)

        except Exception as e:
            self.logger.warning(f'Error parsing packet: {e}')
            return

    def send_offer(self, packet: DHCPPacket) -> None:

        try:
            lease = self._srv.create_lease(packet.chaddr)
            response = DHCPPacket.Offer(
                ip=IPv4Address(lease.ip),
                router_ip=self._srv.config.server_router,
                netmask_ip=self._srv.config.server_network.netmask,
                mac=packet.chaddr,
                xid=packet.xid,
                lease_time=self._srv.config.lease_time_second,
                dns_ips=self._srv.config.dns_ips)

        except IPv4UnavailableError as e:
            self.logger.warning(f'No more IP addresses available: {e}')
            response = DHCPPacket.Nak(mac=packet.chaddr, xid=packet.xid)
        except Exception as e:
            self.logger.error(f'(offer) DHCP server error {e}')
            return
        self.broadcast(response)

    def release_lease(self, packet: DHCPPacket) -> None:
        lease = self._srv.get_lease_by_mac(packet.chaddr)
        if self.is_debug:
            self.logger.debug(f'Release for lease:{lease} requested')
        if lease is not None:
            self._srv.remove_lease(lease)

    def send_ack(self, packet: DHCPPacket) -> None:
        try:
            if packet.ciaddr > 0:
                requested_ip = IPv4Address(packet.ciaddr)
                if self.is_debug:
                    self.logger.debug(
                        f'renew lease request for {requested_ip}')
                lease = self._srv.get_lease_by_mac(packet.chaddr)
                if lease is None:
                    if self.is_debug:
                        self.logger.debug(
                            f'no lease found for {packet.chaddr}. sending NAK')
                    return self.send_nak(packet)
                if lease.ip != packet.ciaddr:
                    if self.is_debug:
                        self.logger.debug(
                            f'lease IP mismatch: {lease.ip} != {packet.ciaddr}. sending NAK'
                        )
                    return self.send_nak(packet)

                self._srv.renew_lease(lease)

            else:
                req_ip = packet.get_option_value(dhcp.DHCP_OPT_REQ_IP)
                if req_ip is None:
                    if self.is_debug:
                        self.logger.debug(f'No requested IP. Sending NAK')
                    return self.send_nak(packet)

                requested_ip = IPv4Address(req_ip)
                if self.is_debug:
                    self.logger.debug(f'new IP request: {requested_ip}')

                if self._srv.is_ip_available(requested_ip) is False:
                    if self.is_debug:
                        self.logger.info(
                            f'Requested IP {requested_ip} is not available. sending NAK'
                        )
                    return self.send_nak(packet)
                lease = self._srv.create_lease(packet.chaddr, requested_ip)
                self._srv.add_lease(lease)

            response = DHCPPacket.Ack(
                ip=requested_ip,
                router_ip=self._srv.config.server_router,
                netmask_ip=self._srv.config.server_network.netmask,
                mac=packet.chaddr,
                xid=packet.xid,
                lease_time=self._srv.config.lease_time_second,
                dns_ips=self._srv.config.dns_ips)

            self.broadcast(response)

        except IPv4UnavailableError as e:
            if self.is_debug:
                self.logger.info(f'requested IP is unavailable: {e}')
            self.send_nak(packet)
        except Exception as e:
            self.logger.error(f'(ack) DHCP server error {e}')
            return

    def send_nak(self, packet: DHCPPacket) -> None:

        response = DHCPPacket.Nak(mac=packet.chaddr, xid=packet.xid)
        self.broadcast(response)
