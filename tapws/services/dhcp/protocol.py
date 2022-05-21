#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
from asyncio.transports import DatagramTransport
from ipaddress import IPv4Address
from typing import TYPE_CHECKING

import macaddress

from .lease import Lease

if TYPE_CHECKING:
    from .server import DHCPServer

from dpkt import Error as DpktError

from .packet import DHCPPacket, IPv4UnavailableError, dhcp


class DHCPServerProtocol(asyncio.DatagramProtocol):

    broadcast_ip = '255.255.255.255'
    broadcast_port = 68

    def __init__(self, server: 'DHCPServer') -> None:
        self.server = server
        self._response_map = {
            dhcp.DHCPDISCOVER: self.send_offer,
            dhcp.DHCPREQUEST: self.send_response,
            dhcp.DHCPRELEASE: self.release_lease,
            dhcp.DHCPDECLINE: self.reinitialize_lease,
        }
        logger = logging.getLogger('tapws.dhcp')
        self.is_debug = logger.isEnabledFor(logging.DEBUG)
        self.logger = logger

    async def broadcast(self, packet: DHCPPacket) -> None:
        if self.is_debug:
            self.logger.debug(f'Broadcasting: {repr(packet)}')
        self.transport.sendto(bytes(packet),
                              (self.broadcast_ip, self.broadcast_port))

    def connection_made(self, transport: DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        allowed_requests = self._response_map.keys()

        try:
            packet = DHCPPacket(data)
            if packet.request_type not in allowed_requests:
                if self.is_debug:
                    self.logger.debug(
                        f'Unknown request type: {packet.request_type}')
                return

            mac = macaddress.parse(packet.chaddr, macaddress.OUI,
                                   macaddress.MAC)
            if self.is_debug:
                self.logger.debug(
                    f'Incoming packet: {repr(packet)}. Mac: {mac}')

            cmd = self._response_map.get(packet.request_type, None)
            if cmd:
                asyncio.create_task(cmd(packet))

        except DpktError as e:
            if self.is_debug:
                self.logger.debug(f'Invalid packet: {e}')
        except ValueError as e:
            if self.is_debug:
                self.logger.debug(f'Invalid packet: {e}')
            return
        except Exception as e:
            self.logger.warning(f'Error parsing packet: {e}')
            return

    async def send_offer(self, packet: DHCPPacket) -> None:

        try:
            selected_ip = self.server.get_usable_ip()
            temp_lease = Lease(mac=packet.chaddr,
                               ip=int(selected_ip),
                               lease_time=self.server.config.lease_time)

            response = DHCPPacket.Offer(ip=IPv4Address(temp_lease.ip),
                                        mac=packet.chaddr,
                                        secs=packet.secs,
                                        xid=packet.xid,
                                        **self.server.config.dhcp_opts())

        except IPv4UnavailableError as e:
            self.logger.warning(f'No more IP addresses available: {e}')
            return
        except Exception as e:
            self.logger.error(f'(offer) DHCP server error {e}')
            return
        await self.broadcast(response)

    async def release_lease(self, packet: DHCPPacket) -> None:
        lease = self.server.get_lease_by_mac(packet.chaddr)
        if self.is_debug:
            self.logger.debug(f'Release for lease:{lease} requested')
        if lease is not None:
            self.server.remove_lease(lease)

    async def reinitialize_lease(self, packet: DHCPPacket) -> None:
        """
        Reinitialize lease for client. The ACK is sent to client and the client detects ARP conflict (IP already in use by other client).
        Resend ACK to the client.
        """
        if self.is_debug:
            self.logger.debug(f'DHCPDECLINE recieved: {packet.chaddr}')

        if self.validate_server_id(packet) is False:
            return

        lease = self.server.get_lease_by_mac(packet.chaddr)
        if lease and lease.ip == packet.ciaddr:
            if self.is_debug:
                self.logger.debug(f'Reinitialize lease for client: {lease}')

            # If lease found, delete it and let `send_response` take care of it
            await self.release_lease(packet)

        return await self.send_response(packet)

    async def send_response(self, packet: DHCPPacket) -> None:
        try:
            if self.validate_server_id(packet) is False:
                return

            # Prioritize client's IP address options over ciaddr
            client_ip_int_or_byte = packet.get_option_value(
                dhcp.DHCP_OPT_REQ_IP) or packet.ciaddr

            client_ip = IPv4Address(client_ip_int_or_byte)

            if self.is_debug:
                self.logger.debug(f'Client IP: {client_ip}')
                self.logger.debug(
                    f'ciaddr: {packet.ciaddr}. If it is not zero, we already know each other.'
                )
                self.logger.debug(
                    f'Requested IP (OPT): {client_ip_int_or_byte}.')

            lease = self.server.get_lease_by_mac(packet.chaddr)
            if lease:
                self.server.renew_lease(lease)
            else:
                # ensure ip is available
                if self.server.is_ip_available(client_ip) == False:
                    raise IPv4UnavailableError(
                        f'IP {client_ip} is already in use by another client')

                lease = Lease(mac=packet.chaddr,
                              ip=int(client_ip),
                              lease_time=self.server.config.lease_time)

                self.server.add_lease(lease)

            response = DHCPPacket.Ack(ip=client_ip,
                                      mac=packet.chaddr,
                                      secs=packet.secs,
                                      xid=packet.xid,
                                      **self.server.config.dhcp_opts())

            await self.broadcast(response)

        except IPv4UnavailableError as e:
            if self.is_debug:
                self.logger.info(f'requested IP is unavailable: {e}')
            await self.send_nak(packet)
        except ValueError as e:
            if self.is_debug:
                self.logger.debug(f'Value error: {e}')
            await self.send_nak(packet)
        except Exception as e:
            self.logger.error(f'(ack) DHCP server error {e}')
            return

    def validate_server_id(self, packet: DHCPPacket) -> bool:
        """ 
        Validate server id in the packet. 
        If server id is present and it is not equal to the server id, return False.
        """

        server_id = packet.get_option_value(dhcp.DHCP_OPT_SERVER_ID)
        if server_id and server_id != self.server.config.server_ip.packed:
            if self.is_debug:
                self.logger.debug(
                    f'Server ID missmatch with server IP. Probably it is not for us.'
                )
            return False
        return True

    async def send_nak(self, packet: DHCPPacket) -> None:

        response = DHCPPacket.Nak(mac=packet.chaddr, xid=packet.xid)
        await self.broadcast(response)
