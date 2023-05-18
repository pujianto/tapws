#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
from asyncio.transports import DatagramTransport
from functools import partial
from ipaddress import IPv4Address
from typing import TYPE_CHECKING
import typing

from .lease import Lease

if TYPE_CHECKING:
    from .server import DHCPServer

from dpkt import Error as DpktError

from .packets import DHCPPacket, IPv4UnavailableError, dhcp


class DHCPServerProtocol(asyncio.DatagramProtocol):
    broadcast_ip = "255.255.255.255"
    broadcast_port = 68
    response_map: typing.Dict[int, typing.Callable]

    __slots__ = (
        "server",
        "response_map",
        "allowed_requests",
        "logger",
        "is_debug",
        "transport",
    )

    def __init__(
        self,
        server: "DHCPServer",
        *,
        logger: logging.Logger = logging.getLogger("tapws.dhcp.protocol"),
    ) -> None:
        self.server = server
        self.response_map = {
            dhcp.DHCPDISCOVER: self.send_offer,
            dhcp.DHCPREQUEST: self.send_response,
            dhcp.DHCPRELEASE: self.release_lease,
            dhcp.DHCPDECLINE: self.reinitialize_lease,
        }
        self.logger = logger

        self.allowed_requests = self.response_map.keys()
        self.is_debug = self.logger.isEnabledFor(logging.DEBUG)

    async def broadcast(self, packet: DHCPPacket) -> None:
        if self.is_debug:
            self.logger.debug(f"Broadcasting: {repr(packet)}")
        self.transport.sendto(bytes(packet), (self.broadcast_ip, self.broadcast_port))

    def connection_made(self, transport: DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            packet = DHCPPacket(data)
            if self.is_debug:
                self.logger.debug(f"Received: {repr(packet)}")
            if packet.request_type not in self.allowed_requests:
                if self.is_debug:
                    self.logger.debug(f"Unknown request type: {packet.request_type}")
                return

        except DpktError as e:
            if self.is_debug:
                self.logger.debug(f"Invalid packet: {e}")
            return
        except ValueError as e:
            if self.is_debug:
                self.logger.debug(f"Invalid packet: {e}")
            return
        except Exception as e:
            self.logger.warning(f"Error parsing packet: {e}")
            return
        cmd = self.response_map.get(packet.request_type)
        if cmd:
            asyncio.create_task(cmd(packet), name="broadcast").add_done_callback(
                partial(self._on_send_done)
            )

    def _on_send_done(self, future: asyncio.Future) -> None:
        if future.exception():
            self.logger.warning(f"Error sending packet: {future.exception()}")

    async def send_offer(self, packet: DHCPPacket) -> None:
        try:
            selected_ip = await self.server.get_available_ip()

        except IPv4UnavailableError as e:
            self.logger.warning(f"No more IP addresses available: {e}")
            self.logger.info("Tips: increase the pool size (reduce the subnet size)")
            return

        response = DHCPPacket.Offer(
            ip=selected_ip,
            mac=packet.chaddr,
            secs=packet.secs,
            xid=packet.xid,
            **self.server.config.dhcp_opts(),
        )
        await self.broadcast(response)

    async def release_lease(self, packet: DHCPPacket) -> None:
        lease = await self.server.get_lease_by_mac(packet.chaddr)

        if lease is not None:
            await self.server.remove_lease(lease)

    async def reinitialize_lease(self, packet: DHCPPacket) -> None:
        """
        Reinitialize lease for client. The ACK is sent to client and the client detects ARP conflict (IP already in use by other client).
        Resend ACK to the client.
        """
        if self.validate_server_id(packet) is False:
            return

        lease = await self.server.get_lease_by_mac(packet.chaddr)
        if lease and lease.ip == packet.ciaddr:
            # If lease found, delete it and let `send_response` take care of it
            await self.release_lease(packet)

        return await self.send_response(packet)

    async def send_response(self, packet: DHCPPacket) -> None:
        if self.validate_server_id(packet) is False:
            return

        try:
            # Prioritize client's IP address options over ciaddr
            client_ip_int_or_byte = (
                packet.get_option_value(dhcp.DHCP_OPT_REQ_IP) or packet.ciaddr
            )

            client_ip = IPv4Address(client_ip_int_or_byte)

            if self.is_debug:
                self.logger.debug(f"requested IP: {client_ip}.")

            lease = await self.server.get_lease_by_mac(packet.chaddr)
            if lease:
                await self.server.renew_lease(lease)
            else:
                # ensure ip is available
                if await self.server.is_ip_available(client_ip) == False:
                    raise IPv4UnavailableError(
                        f"IP {client_ip} is already in use by another client"
                    )

                lease = Lease(
                    mac=packet.chaddr,
                    ip=int(client_ip),
                    lease_time=self.server.config.lease_time,
                )

                await self.server.add_lease(lease)

        except IPv4UnavailableError as e:
            if self.is_debug:
                self.logger.info(f"requested IP is unavailable: {e}")
            await self.send_nak(packet)
            return

        except ValueError as e:
            if self.is_debug:
                self.logger.debug(f"Value error: {e}")
            await self.send_nak(packet)
            return

        except Exception as e:
            self.logger.error(f"(ack) DHCP server error {e}")
            return

        response = DHCPPacket.Ack(
            ip=client_ip,
            mac=packet.chaddr,
            secs=packet.secs,
            xid=packet.xid,
            **self.server.config.dhcp_opts(),
        )

        await self.broadcast(response)

    def validate_server_id(self, packet: DHCPPacket) -> bool:
        """
        Validate server id in the packet.
        If server id is present and it is not equal to the server id, return False.
        """

        server_id = packet.get_option_value(dhcp.DHCP_OPT_SERVER_ID)
        if server_id and server_id != self.server.config.server_ip.packed:
            if self.is_debug:
                self.logger.debug(
                    f"Server ID missmatch with server IP. Probably it is not for us."
                )
            return False
        return True

    async def send_nak(self, packet: DHCPPacket) -> None:
        response = DHCPPacket.Nak(mac=packet.chaddr, xid=packet.xid)
        await self.broadcast(response)
