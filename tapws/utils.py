#!/usr/bin/env python
# -*- coding: utf-8 -*-


def format_mac(data: bytes) -> str:
    return ':'.join('{0:02x}'.format(a) for a in data)
