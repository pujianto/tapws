#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import ipaddress
import logging
import ssl
from asyncio import create_task
from functools import partial
from ipaddress import IPv4Address
from typing import List, Optional

import iptc
from pytun import IFF_NO_PI, IFF_TAP
from pytun import Error as TunError
from pytun import TunTapDevice
from websockets import exceptions as websockets_exceptions
from websockets.server import WebSocketServerProtocol
from websockets.server import serve as websockets_serve

from .services.base import BaseService as TapwsService
from .utils import format_mac


class Connection:
    _mac = None

    def __init__(self,
                 websocket: WebSocketServerProtocol,
                 mac: Optional[str] = None) -> None:
        self._mac = mac
        self.websocket = websocket

    def __repr__(self) -> str:
        return f'Connection({self.websocket.id})'

    @property
    def mac(self) -> Optional[str]:
        return self._mac

    @mac.setter
    def mac(self, mac) -> None:
        self._mac = mac


class Server:
    _svcs = []

    def __init__(
        self,
        interface_ip: IPv4Address,
        interface_subnet: int,
        interface_name: str,
        host: str = '0.0.0.0',
        port: int = 8080,
        public_interface_name: Optional[str] = None,
        ssl: Optional[ssl.SSLContext] = None,
        services: Optional[List[TapwsService]] = None,
    ) -> None:

        self.host = host
        self.port = port

        self.iface_name = interface_name
        self.iface_ip = str(interface_ip)
        self.iface_network = ipaddress.ip_network(
            f'{self.iface_ip}/{interface_subnet}', strict=False)

        self.tap = TunTapDevice(self.iface_name, flags=(IFF_TAP | IFF_NO_PI))
        self.tap.addr = str(self.iface_ip)
        self.tap.netmask = str(self.iface_network.netmask)
        self.tap.mtu = 1500
        self.hw_addr = format_mac(self.tap.hwaddr)
        self.public_iface_name = public_interface_name

        if services is not None:
            for service in services:
                self._svcs.append(service)

        self._connections = set()
        self.ssl = ssl
        self.loop = asyncio.get_running_loop()
        # refs: https://www.iana.org/assignments/ethernet-numbers/ethernet-numbers.xhtml
        self.broadcast_addr = 'ff:ff:ff:ff:ff:ff'
        self.whitelist_macs = ('33:33:', '01:00:5e:', '00:52:02:')

    def broadcast(self) -> None:
        message = self.tap.read(1024 * 4)
        dst_mac = format_mac(message[:6])

        for connection in self._connections.copy():
            try:
                logging.debug(
                    f'Sending to {dst_mac} | connection: {connection.mac} | hwaddr: {self.hw_addr}'
                )

                if dst_mac in [self.broadcast_addr, connection.mac]:
                    create_task(connection.websocket.send(message))
                    continue

                if dst_mac.startswith(self.whitelist_macs):
                    create_task(connection.websocket.send(message))
                    continue

            except Exception as e:
                logging.error(f'Error broadcasting message to client: {e}')

    async def websocket_handler(self,
                                websocket: WebSocketServerProtocol) -> None:
        connection = Connection(websocket, None)
        self._connections.add(connection)
        try:
            async for message in websocket:
                mac = format_mac(message[6:12])
                logging.debug(
                    f'incoming from {mac} | connection: {connection.mac} | hwaddr: {self.hw_addr}'
                )
                connection.mac = mac
                try:
                    self.tap.write(message)
                except TunError as e:
                    logging.error(f'Error writing to device: {e}')
                except Exception as e:
                    logging.error(f'Unknown error writing to device: {e}')

        except websockets_exceptions.ConnectionClosed as e:
            logging.debug(f'Client disconnected: {e}')
        except Exception as e:
            logging.error(e)
        finally:
            self._connections.remove(connection)

    def bootstrap_netfilter(self) -> None:
        logging.info('Bootstrapping netfilter (iptables) rules ...')

        forward_chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), 'FORWARD')

        ingress_rule = iptc.Rule()
        ingress_rule.in_interface = self.public_iface_name
        ingress_rule.out_interface = self.iface_name

        ingress_rule_filter = iptc.Match(ingress_rule, 'state')
        ingress_rule_filter.state = 'RELATED,ESTABLISHED'

        ingress_rule.add_match(ingress_rule_filter)
        ingress_rule.target = iptc.Target(ingress_rule, 'ACCEPT')

        egress_rule = iptc.Rule()
        egress_rule.in_interface = self.iface_name
        egress_rule.out_interface = self.public_iface_name
        egress_rule.target = iptc.Target(egress_rule, 'ACCEPT')

        postrouting_chain = iptc.Chain(iptc.Table(iptc.Table.NAT),
                                       'POSTROUTING')
        translation_rule = iptc.Rule()
        translation_rule.out_interface = self.public_iface_name
        translation_rule.target = iptc.Target(translation_rule, 'MASQUERADE')

        forward_chain.insert_rule(ingress_rule)
        forward_chain.insert_rule(egress_rule)
        postrouting_chain.insert_rule(translation_rule)

    async def start(self) -> None:
        self.tap.up()
        logging.info('Starting service...')

        self.loop.add_reader(self.tap.fileno(), partial(self.broadcast))

        ws = websockets_serve(self.websocket_handler,
                              self.host,
                              self.port,
                              ssl=self.ssl)
        self.ws_server = await ws

        if self.public_iface_name is not None:
            self.bootstrap_netfilter()

        for service in self._svcs:
            await service.start()
        await self.ws_server.wait_closed()

    async def stop(self) -> None:

        for service in self._svcs:
            await service.stop()
        self.ws_server.close()
        self.tap.close()
