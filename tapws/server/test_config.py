#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .config import ServerConfig
import unittest
import unittest.mock


class TestServerConfig(unittest.TestCase):
    def setUp(self) -> None:
        self.env_dict = {
            "WITH_SSL": "False",
            "HOST": "1.2.3.4",
            "PORT": "1234",
            "PUBLIC_INTERFACE": "a",
            "INTERFACE_IP": "2.3.4.5",
            "INTERFACE_SUBNET": "24",
            "WITH_DHCP": "True",
            "DHCP_LEASE_TIME": "3600",
        }
        return super().setUp()

    def testConfig(self):
        env_dict = self.env_dict.copy()

        with unittest.mock.patch.dict("os.environ", env_dict):
            server_config = ServerConfig.From_env()
            self.assertIsInstance(server_config, ServerConfig)
            self.assertEqual(
                str(server_config),
                f"ServerConfig(ip={server_config.host}, port={server_config.port}...)",
            )

    def testInvalidHostIPRaisesValueError(self):
        env_dict = self.env_dict.copy()
        env_dict.update({"HOST": "invalid value"})

        with unittest.mock.patch.dict("os.environ", env_dict), self.assertRaises(
            ValueError
        ):
            ServerConfig.From_env()

    def testWithSSLContext(self):
        import ssl

        env_dict = self.env_dict.copy()
        env_dict.update({"WITH_SSL": "True"})

        fake_ssl_context_return = unittest.mock.Mock(spec=ssl.SSLContext)
        fake_ssl_context = unittest.mock.Mock(return_value=fake_ssl_context_return)
        fake_ssl_context.load_cert_chain.return_value = None

        with unittest.mock.patch.dict("os.environ", env_dict), unittest.mock.patch(
            "os.path.isfile", return_value=True
        ), unittest.mock.patch("ssl.SSLContext", fake_ssl_context):
            server_config = ServerConfig.From_env()
            self.assertEqual(server_config.ssl, fake_ssl_context_return)

    def testAssertValueErrors(self):
        env_dict = self.env_dict.copy()
        env_dict.update({"WITH_SSL": "True"})

        update_dict_items = [
            {"SSL_CERT_PATH": ""},
            {"SSL_KEY_PATH": ""},
            {"INTERFACE_SUBNET": "32"},
            {"INTERFACE_SUBNET": "-1"},
            {"DHCP_LEASE_TIME": "-2"},
        ]

        import ssl

        fake_ssl_context_return = unittest.mock.Mock(spec=ssl.SSLContext)
        fake_ssl_context = unittest.mock.Mock(return_value=fake_ssl_context_return)
        fake_ssl_context.load_cert_chain.return_value = None

        with unittest.mock.patch.dict("os.environ", env_dict), unittest.mock.patch(
            "os.path.isfile", return_value=True
        ), unittest.mock.patch("ssl.SSLContext", fake_ssl_context):
            for update_dict in update_dict_items:
                with unittest.mock.patch.dict(
                    "os.environ", update_dict
                ), self.assertRaises(ValueError):
                    ServerConfig.From_env()

        with unittest.mock.patch.dict("os.environ", env_dict), unittest.mock.patch(
            "os.path.isfile", return_value=False
        ):
            with self.assertRaises(ValueError):
                ServerConfig.From_env()
