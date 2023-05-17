#!/usr/bin/env python
# -*- coding: utf-8 -*-
import abc


class BaseService(object):  # pragma: no cover

    """
    Base class for tapws services.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self) -> None:
        pass

    @abc.abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError
