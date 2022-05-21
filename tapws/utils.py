#!/usr/bin/env python
# -*- coding: utf-8 -*-

import macaddress


def format_mac(data: bytes) -> str | ValueError:
    return str(macaddress.MAC(data)).lower().replace('-', ':')
