#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import ipaddress
import logging
import socket
from functools import partial

import dhcppython
from dhcppython.packet import DHCPPacket

from .base import BaseService


class NotImplementedError(Exception):
    pass


class DHCPServerProtocol(asyncio.DatagramProtocol):

    def __init__(self):
        self._handlers = {
            'DHCPDISCOVER': self.sendOffer,
            'DHCPREQUEST': self.sendAck,
        }

    packets = []

    def sendOffer(self, packet):
        option_list = dhcppython.options.OptionList()
        option_list.insert(
            0, dhcppython.options.MessageType(code=53, length=1, data=b'\x02'))

        option_list.insert(
            1,
            dhcppython.options.SubnetMask(
                code=1,
                length=4,
                data=ipaddress.IPv4Address('255.255.255.0').packed))
        option_list.insert(
            2,
            dhcppython.options.RenewalTime(code=58,
                                           length=4,
                                           data=b'\x00\x01Q\x80'))
        option_list.insert(
            3,
            dhcppython.options.RebindingTime(code=59,
                                             length=4,
                                             data=b'\x00\x01Q\x80'))
        option_list.insert(
            4,
            dhcppython.options.IPAddressLeaseTime(code=51,
                                                  length=4,
                                                  data=b'\x00\x01Q\x80'))
        option_list.insert(
            5,
            dhcppython.options.ServerIdentifier(
                code=54,
                length=4,
                data=ipaddress.IPv4Address('10.11.12.1').packed))
        option_list.insert(
            6, dhcppython.options.End(code=255, length=0, data=b''))

        resp = DHCPPacket.Offer(packet.chaddr,
                                seconds=0,
                                tx_id=packet.xid,
                                use_broadcast=True,
                                yiaddr=ipaddress.IPv4Address('10.11.12.3'),
                                option_list=option_list)
        return resp

    def sendAck(self, packet):
        raise NotImplementedError

    def _build_response(self, packet):
        for option in packet.options:
            if isinstance(option, dhcppython.options.MessageType):
                handler = self._handlers.get(
                    option.value.get('dhcp_message_type'), self.handle_unknown)
                return handler(packet)
        logging.error(f'No handler for packet: {packet.options} {packet}')
        return self.handle_unknown(packet)

    def handle_unknown(self, packet):
        logging.warning(f'Unknown DHCP packet: {packet}')
        return None

    def error_received(self, exc):
        logging.warning(f'Error received: {exc}')

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        h, p = addr
        logging.debug(f'HOST {h} PORT {p}')

        try:
            packet = DHCPPacket.from_bytes(data)
            logging.debug(f'received dhcp packet: {packet}')
            response = self._build_response(packet)
            if response:
                logging.debug(f'our resp: {response}')
                self.transport.sendto(packet.asbytes, ('255.255.255.255', p))

        except Exception as e:
            logging.warning(f'Error parsing DHCP packet: {e}')


class DhcpServer(BaseService):

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.loop = asyncio.get_running_loop()
        asyncio.create_task(self._ainit())

    async def _ainit(self):

        logging.info('Starting DHCP service')
        factory = partial(DHCPServerProtocol)
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(
            lambda: factory(),
            local_addr=(self.ip, self.port),
            family=socket.AF_INET,
            allow_broadcast=True)

        sock = self.transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        name = '%s:%d' % self.transport.get_extra_info('socket').getsockname()
        logging.info(f'DHCP listening on {name}')

    def close(self):
        self.transport.close()
