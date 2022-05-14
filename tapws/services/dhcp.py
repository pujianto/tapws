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

    def __init__(self, server):
        self._handlers = {
            'DHCPDISCOVER': self.sendOffer,
            'DHCPREQUEST': self.sendAck,
        }
        self.server = server

    def sendOffer(self, packet):

        resp = DHCPPacket.Offer(
            'ff:ff:ff:ff:ff:ff',
            tx_id=packet.xid,
            seconds=0,
            yiaddr=ipaddress.IPv4Address('10.11.12.3').packed,
        )

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
        logging.info('Connection made')

    def datagram_received(self, data, addr):
        h, p = addr
        logging.debug(f'HOST {h} PORT {p}')

        try:
            packet = DHCPPacket.from_bytes(bytes(data))
            logging.debug(f'received dhcp packet:')
            logging.debug(packet.view_packet())
            response = self._build_response(packet)
            if response:
                logging.debug(f'our resp:')
                logging.debug(f'{response.view_packet()}')
                self.transport.sendto(packet.asbytes, ('255.255.255.255', p))

        except Exception as e:
            logging.warning(f'Error parsing DHCP packet: {e}')
            raise e


class DhcpServer(BaseService):

    def __init__(self, ip, port, tap_name=b'tap0'):
        self.ip = ip
        self.port = port
        self.loop = asyncio.get_running_loop()
        self.tap_name = tap_name
        asyncio.create_task(self._ainit())

    async def _ainit(self):

        logging.info('Starting DHCP service')
        factory = partial(DHCPServerProtocol, self)
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(
            lambda: factory(),
            local_addr=('0.0.0.0', self.port),
            allow_broadcast=True)

        self.transport.get_extra_info('socket').setsockopt(
            socket.SOL_SOCKET, 25, self.tap_name)

        name = '%s:%d' % self.transport.get_extra_info('socket').getsockname()
        logging.info(f'DHCP listening on {name}')

    def close(self):
        self.transport.close()
