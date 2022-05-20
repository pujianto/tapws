#!/usr/bin/env python
# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from typing import Type


class BaseService(ABC):
    """
    Base class for tapws services.
    """

    def __init__(self) -> None:
        pass

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError


TypeBaseService = Type[BaseService]
