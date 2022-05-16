#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
from asyncio.transports import DatagramTransport
from typing import Optional

from .utils import DHCPPacket, IPv4UnavailableError, dhcp


class DHCPServerProtocol(asyncio.DatagramProtocol):

    broadcast_ip = '255.255.255.255'
    broadcast_port = 68
    broadcast_mac = 'ff:ff:ff:ff:ff:ff'

    def __init__(self, server) -> None:
        self._srv = server
        self._response_map = {
            'discover': self._send_offer,
            'request': self._send_ack,
        }

    def broadcast(self, data: bytes) -> None:
        self.transport.sendto(data, (self.broadcast_ip, self.broadcast_port))

    def connection_made(self, transport: DatagramTransport) -> None:
        self.transport = transport

    def _send_offer(self, packet: dhcp.DHCP) -> None:

        try:
            lease = self._srv.create_lease(packet.chaddr)

            response = dhcp.DHCP()
            response.chaddr = packet.chaddr
            response.op = dhcp.DHCP_OP_REPLY
            response.xid = packet.xid
            response.yiaddr = lease.ip
            response.siaddr = int(self._srv.ip)

            logging.debug(f'Lease time: {lease.lease_time}')

            lease_time = int(float(lease.lease_time))
            renew_time = int(lease.lease_time / 2)
            rebind_time = int(renew_time + lease_time)

            response.opts = []
            response.opts.append(
                (dhcp.DHCP_OPT_MSGTYPE, bytes(chr(dhcp.DHCPOFFER), 'ascii')))
            response.opts.append(
                (dhcp.DHCP_OPT_NETMASK, self._srv.ip_network.netmask.packed))
            response.opts.append((dhcp.DHCP_OPT_RENEWTIME,
                                  DHCPPacket.seconds_to_bytes(renew_time)))
            response.opts.append((dhcp.DHCP_OPT_REBINDTIME,
                                  DHCPPacket.seconds_to_bytes(rebind_time)))
            response.opts.append((dhcp.DHCP_OPT_LEASE_SEC,
                                  DHCPPacket.seconds_to_bytes(lease_time)))
            response.opts.append(
                (dhcp.DHCP_OPT_SERVER_ID, self._srv.ip.packed))
            response.opts.append((dhcp.DHCP_OPT_ROUTER, self._srv.ip.packed))
            response.opts.append(
                (dhcp.DHCP_OPT_DNS_SVRS,
                 b''.join(dns.packed for dns in self._srv.dns_ips)))

            self.broadcast(bytes(response))

        except IPv4UnavailableError as e:
            logging.warning(f'No more IP addresses available: {e}')
            return None

    def _send_nack(self, packet: dhcp.DHCP) -> None:
        response = dhcp.DHCP()
        response.chaddr = packet.chaddr
        response.op = dhcp.DHCP_OP_REPLY
        response.xid = packet.xid
        response.opts = []
        response.opts.append(
            (dhcp.DHCP_OPT_MSGTYPE, bytes(chr(dhcp.DHCPNAK), 'ascii')))
        self.broadcast(bytes(response))

    def _send_ack(self, packet: dhcp.DHCP) -> None:
        try:
            requested_ip = DHCPPacket.get_requested_ip(packet)
            if requested_ip is None:
                return None

            logging.debug(f'Requested IP: {requested_ip}')

            if not self._srv.is_ip_available(requested_ip):
                logging.warning(
                    f'Requested IP {requested_ip} is not available. sending NACK'
                )
                return self._send_nack(packet)

            lease = self._srv.create_lease(packet.chaddr, requested_ip)

            response = dhcp.DHCP()
            response.chaddr = packet.chaddr
            response.op = dhcp.DHCP_OP_REPLY
            response.xid = packet.xid
            response.yiaddr = lease.ip
            response.siaddr = int(self._srv.ip)

            lease_time = int(float(lease.lease_time))
            renew_time = int(lease.lease_time / 2)
            rebind_time = int(renew_time + lease_time)

            response.opts = []
            response.opts.append(
                (dhcp.DHCP_OPT_MSGTYPE, bytes(chr(dhcp.DHCPACK), 'ascii')))
            response.opts.append(
                (dhcp.DHCP_OPT_NETMASK, self._srv.ip_network.netmask.packed))
            response.opts.append((dhcp.DHCP_OPT_RENEWTIME,
                                  DHCPPacket.seconds_to_bytes(renew_time)))
            response.opts.append((dhcp.DHCP_OPT_REBINDTIME,
                                  DHCPPacket.seconds_to_bytes(rebind_time)))
            response.opts.append((dhcp.DHCP_OPT_LEASE_SEC,
                                  DHCPPacket.seconds_to_bytes(lease_time)))
            response.opts.append(
                (dhcp.DHCP_OPT_SERVER_ID, self._srv.ip.packed))
            response.opts.append((dhcp.DHCP_OPT_ROUTER, self._srv.ip.packed))
            response.opts.append(
                (dhcp.DHCP_OPT_DNS_SVRS,
                 b''.join(dns.packed for dns in self._srv.dns_ips)))

            self._srv.add_lease(lease)
            logging.debug(f'New lease registered: {lease}')

            self.broadcast(bytes(response))

        except IPv4UnavailableError as e:
            logging.warning(f'No more IP addresses available: {e}')
            return None

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            packet = DHCPPacket.unpack(data)
            logging.debug(f'Incoming packet: {repr(packet)}')

            request_type = DHCPPacket.request_type(packet)
            logging.debug(f'request_type: {request_type}')

            response = self._build_response(request_type, packet)

            if response is not None:
                self.broadcast(bytes(response))
        except Exception as e:
            logging.warning(f'Error parsing packet: {e}')

    def _build_response(self, request_type, packet) -> Optional[dhcp.DHCP]:

        return self._response_map.get(request_type,
                                      lambda packet: None)(packet)
