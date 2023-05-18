#!/usr/bin/env python
# -*- coding: utf-8 -*-

import macaddress


def format_mac(data: bytes) -> str:
    """
    Format MAC address from bytes to string.
    :return: MAC address in format xx:xx:xx:xx:xx:xx
    :rtype: str
    :exception: ValueError
    """
    return str(macaddress.MAC(data)).lower().replace("-", ":")
