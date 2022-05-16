#!/usr/bin/env python
# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractmethod
from typing import Type


class BaseService(metaclass=ABCMeta):
    """
    Base class for tapws services.
    """

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError


TypeBaseService = Type[BaseService]
