#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pytun import IFF_NO_PI, IFF_TAP, TunTapDevice


def create_tap_device(name='tap0', **kwargs):
    """
    Create a tap device.
    """

    ip = kwargs.get('ip', '10.11.12.1')
    netmask = kwargs.get('netmask', '255.255.255.0')
    mtu = kwargs.get('mtu', 1500)

    device = TunTapDevice(name, flags=(IFF_TAP | IFF_NO_PI))
    device.addr = ip
    device.netmask = netmask
    device.mtu = mtu

    return device
