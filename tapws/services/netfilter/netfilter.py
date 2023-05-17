#!/usr/local/env python
# -*- coding: utf-8 -*-
import logging

import iptc

from ..base import BaseService


class Netfilter(BaseService):
    __slots__ = ("public_interface", "private_interface", "logger", "is_debug")

    def __init__(
        self,
        public_interface: str,
        private_interface: str,
        *,
        logger: logging.Logger = logging.getLogger("tawps.netfilter")
    ) -> None:
        self.public_interface = public_interface
        self.private_interface = private_interface
        self.logger = logger
        self.is_debug = self.logger.isEnabledFor(logging.DEBUG)

    def bootstrap_netfilter(self) -> None:
        forward_chain = iptc.Chain(iptc.Table(iptc.Table.FILTER), "FORWARD")

        ingress_rule = iptc.Rule()
        ingress_rule.in_interface = self.public_interface
        ingress_rule.out_interface = self.private_interface

        ingress_rule_filter = iptc.Match(ingress_rule, "state")
        ingress_rule_filter.state = "RELATED,ESTABLISHED"

        ingress_rule.add_match(ingress_rule_filter)
        ingress_rule.target = iptc.Target(ingress_rule, "ACCEPT")

        egress_rule = iptc.Rule()
        egress_rule.in_interface = self.private_interface
        egress_rule.out_interface = self.public_interface
        egress_rule.target = iptc.Target(egress_rule, "ACCEPT")

        postrouting_chain = iptc.Chain(iptc.Table(iptc.Table.NAT), "POSTROUTING")
        translation_rule = iptc.Rule()
        translation_rule.out_interface = self.public_interface
        translation_rule.target = iptc.Target(translation_rule, "MASQUERADE")

        forward_chain.insert_rule(ingress_rule)
        forward_chain.insert_rule(egress_rule)
        postrouting_chain.insert_rule(translation_rule)

    async def up(self) -> None:
        self.logger.info("Bootstrapping netfilter (iptables) rules ...")
        self.bootstrap_netfilter()

    async def down(self) -> None:
        self.logger.info("Cleaning up netfilter (iptables) rules ...")
        iptc.Chain(iptc.Table(iptc.Table.FILTER), "FORWARD").flush()
        iptc.Chain(iptc.Table(iptc.Table.NAT), "POSTROUTING").flush()

    def add_port_forward(
        self, private_port: int, public_port: int, protocol: str, public_ip: str
    ) -> None:
        raise NotImplementedError("not implemented yet")

    def remove_port_forward(
        self, private_port: int, public_port: int, protocol: str, public_ip: str
    ) -> None:
        raise NotImplementedError("not implemented yet")

    start = up
    stop = down
