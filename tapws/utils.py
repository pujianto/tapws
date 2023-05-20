#!/usr/bin/env python
# -*- coding: utf-8 -*-

import macaddress
import asyncio
import logging


def format_mac(data: bytes) -> str:
    """
    Format MAC address from bytes to string.
    :return: MAC address in format xx:xx:xx:xx:xx:xx
    :rtype: str
    :exception: ValueError
    """
    return str(macaddress.MAC(data)).lower().replace("-", ":")


def on_done(
    logger: logging.Logger,
    future: asyncio.Future,
) -> None:
    exception = future.exception()
    if exception:
        logger.warning(f"Exception raised in the future object: {exception}")
