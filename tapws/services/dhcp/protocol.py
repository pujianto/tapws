#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
from asyncio.transports import DatagramTransport
from ipaddress import IPv4Address

from tapws.services.dhcp.server import DHCPServer

from .packet import DHCPPacket, IPv4UnavailableError, dhcp


class DHCPServerProtocol(asyncio.DatagramProtocol):

    broadcast_ip = '255.255.255.255'
    broadcast_port = 68

    def __init__(self, server: DHCPServer) -> None:
        self._srv = server
        self._response_map = {
            dhcp.DHCPDISCOVER: self.send_offer,
            dhcp.DHCPREQUEST: self.send_ack,
        }
        logger = logging.getLogger('tapws.dhcp')
        self.is_debug = logger.isEnabledFor(logging.DEBUG)
        self.logger = logger

    def broadcast(self, data: bytes) -> None:
        if self.is_debug:
            self.logger.debug(f'Broadcasting: {repr(data)}')
        self.transport.sendto(data, (self.broadcast_ip, self.broadcast_port))

    def connection_made(self, transport: DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            packet = DHCPPacket.unpack(data)
            if self.is_debug:
                self.logger.debug(f'Incoming packet: {repr(packet)}')
                self.logger.debug(f'request_type: {packet.request_type}')

            self._response_map.get(packet.request_type,
                                   lambda packet: None)(packet)

        except Exception as e:
            self.logger.warning(f'Error parsing packet: {e}')

    def send_offer(self, packet: dhcp.DHCP) -> None:

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
            response = DHCPPacket.Decline(mac=packet.chaddr)
        except Exception as e:
            self.logger.error(f'DHCP server error {e}')
            return None
        self.broadcast(bytes(response))

    def send_ack(self, packet: DHCPPacket) -> None:
        try:
            req_ip = packet.get_option_value(dhcp.DHCP_OPT_REQ_IP)
            if req_ip is None:
                return self.send_nak(packet)

            requested_ip = IPv4Address(req_ip)
            if self.is_debug:
                self.logger.debug(f'Requested IP: {requested_ip}')

            if not self._srv.is_ip_available(requested_ip):
                self.logger.info(
                    f'Requested IP {requested_ip} is not available. sending NAK'
                )
                return self.send_nak(packet)

            lease = self._srv.create_lease(packet.chaddr, requested_ip)

            response = DHCPPacket.Ack(
                ip=requested_ip,
                router_ip=self._srv.config.server_router,
                netmask_ip=self._srv.config.server_network.netmask,
                mac=packet.chaddr,
                xid=packet.xid,
                lease_time=self._srv.config.lease_time_second,
                dns_ips=self._srv.config.dns_ips)

            self._srv.add_lease(lease)
            self.broadcast(bytes(response))

        except IPv4UnavailableError as e:
            self.logger.warning(f'requested IP is unavailable: {e}')
            self.send_nak(packet)
        except Exception as e:
            self.logger.error(f'DHCP server error {e}')
            return None

    def send_nak(self, packet: dhcp.DHCP) -> None:
        response = dhcp.DHCP()
        response.chaddr = packet.chaddr
        response.op = dhcp.DHCP_OP_REPLY
        response.xid = packet.xid
        response.opts = []
        response.opts.append(
            (dhcp.DHCP_OPT_MSGTYPE, bytes(chr(dhcp.DHCPNAK), 'ascii')))
        self.broadcast(bytes(response))
