#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import ipaddress
import logging
import signal
from functools import partial

import websockets
from dhcppython.packet import DHCPPacket
from pytun import Error as TunError

from .device import create_tap_device
from .utils import async_iter, format_mac, wrap_async


class Connection:

    def __init__(self, websocket, mac=None):
        self.mac = mac
        self.websocket = websocket

    def __repr__(self):
        return f'Connection({self.websocket.id})'


class Server:

    def __init__(self, host='0.0.0.0', port=8080, device=None, ssl=None):
        self.host = host
        self.port = port
        self.connections = set()
        if device is None:
            device = create_tap_device()
            device.up()
        self.tap = device
        self.hw_addr = format_mac(self.tap.hwaddr)
        # refs: https://www.iana.org/assignments/ethernet-numbers/ethernet-numbers.xhtml
        self.broadcast_addr = 'ff:ff:ff:ff:ff:ff'
        self.whitelist_macs = ('33:33:', '01:00:5e:', '00:52:02:')
        self.ws_server = websockets.serve(self.websocket_handler,
                                          self.host,
                                          self.port,
                                          ssl=ssl)
        self.waiter = asyncio.Future()

    async def broadcast(self, message):
        dst_mac = format_mac(message[:6])
        async for connection in async_iter(self.connections):
            try:

                logging.debug(
                    f'Sending to {dst_mac} | connection: {connection.mac} | hwaddr: {self.hw_addr}'
                )

                if dst_mac in [self.broadcast_addr, connection.mac]:
                    await connection.websocket.send(message)
                    continue

                if dst_mac.startswith(self.whitelist_macs):
                    await connection.websocket.send(message)
            except websockets.exceptions.ConnectionClosed:
                logging.debug('client disconnected')
            except Exception as e:
                logging.error(f'Error broadcasting message to client: {e}')

    def tap_read(self):
        try:
            message = self.tap.read(1024 * 4)
            asyncio.create_task(self.broadcast(message))
        except TunError as e:
            logging.error(f'Error reading from device: {e}')
        except Exception as e:
            logging.error(f'Unknown error reading from device: {e}')

    @wrap_async
    def tap_write_async(self, message):
        try:
            self.tap.write(message)
        except TunError as e:
            logging.error(f'Error writing to device: {e}')
        except Exception as e:
            logging.error(f'Unknown error writing to device: {e}')

    async def websocket_handler(self, websocket):
        connection = Connection(websocket, None)
        self.add_connection(connection)
        try:
            async for message in websocket:
                mac = format_mac(message[6:12])
                logging.debug(
                    f'incoming from {mac} | connection: {connection.mac} | hwaddr: {self.hw_addr}'
                )
                connection.mac = mac
                await self.tap_write_async(message)

        except websockets.exceptions.ConnectionClosed as e:
            logging.debug(f'Client disconnected: {e}')
        except Exception as e:
            logging.error(e)
        finally:
            self.remove_connection(connection)

    def add_connection(self, connection):
        self.connections.add(connection)

    def remove_connection(self, connection):
        self.connections.remove(connection)

    def cleanup(self, sig):
        asyncio.create_task(self.stop())

    async def start(self):
        logging.info('Starting server...')
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.cleanup, sig)

        loop.add_reader(self.tap.fileno(), partial(self.tap_read))

        async with self.ws_server:
            await self.waiter
        self.tap.close()

    async def stop(self):
        self.waiter.set_result(None)


class DhcpServerProtocol(asyncio.DatagramProtocol):
    """_summary_
    Support for DHCPv4
    Args:
        asyncio (_type_): _description_
    """

    def __init__(self, max_lease_duration=86400, server=None):
        self.allocated_ips_table = set()
        self.dhcp_cookie = '99.130.83.99'
        pass

    def connection_made(self, transport):
        return super().connection_made(transport)

    def datagram_received(self, data, addr):
        packet = DHCPPacket.from_bytes(data)
        

    def build_dhcp_packet(self):
        pass

    def send_dhcp_offer(self):
        pass

    def send_dhcp_ack(self):
        pass

    def dhcp_release(self):
        pass

    def schedule_release(self):
        pass
