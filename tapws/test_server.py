import unittest
import unittest.mock
from .server import Server, TunError, ServerConfig
from copy import copy
import asyncio


class TestServer(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.ws_server = unittest.mock.AsyncMock()
        self.tuntap = unittest.mock.Mock()
        self.tuntap_cls = unittest.mock.Mock(return_value=self.tuntap)
        self.tuntap.hwaddr = b"abcdef"
        self.tuntap.write = unittest.mock.Mock()
        self.tuntap.fileno = unittest.mock.mock_open()
        self.fake_ws_serve = unittest.mock.AsyncMock()
        self.fake_ws_serve.close = self._helper_sync

        self.fake_ws_cls = unittest.mock.AsyncMock(side_effect=[self.fake_ws_serve])

        self.tuntap_cls = unittest.mock.Mock(return_value=self.tuntap)
        fake_service = unittest.mock.AsyncMock()
        fake_service.start = fake_service.stop = unittest.mock.AsyncMock()
        self.fake_services = [fake_service]
        return super().setUp()

    def _helper_sync(self):
        return None

    async def testStartStop(self):
        server_instance = Server(
            ServerConfig.From_env(),
            self.fake_services,  # type: ignore
            self.tuntap_cls,
            self.fake_ws_cls,  # type: ignore
        )
        await server_instance.start()
        self.assertIs(False, server_instance._waiter_.done())
        await server_instance.stop()
        self.assertIsNone(server_instance._waiter_.result())

    async def testBlockingState(self):
        server_instance = Server(
            ServerConfig.From_env(),
            self.fake_services,  # type: ignore
            self.tuntap_cls,
            self.fake_ws_cls,  # type: ignore
        )
        async with server_instance as s:
            self.assertIsInstance(s._waiter_, asyncio.Future)

    async def testTunError(self):
        tun = unittest.mock.Mock(side_effect=[TunError(2, "err message")])

        with self.assertRaises(TunError):
            Server(
                ServerConfig.From_env(),
                self.fake_services,  # type: ignore
                tuntap_device_cls=tun,
                ws_cls=self.fake_ws_cls,  # type: ignore
                logger=unittest.mock.Mock(),
            )

    async def testCallWithAwait(self):
        async def _helper_stop_instance(instance: Server):
            self.assertFalse(instance._waiter_.done())
            await asyncio.sleep(0.1)
            await instance.stop()
            self.assertTrue(instance._waiter_.done())

        server_instance = Server(
            ServerConfig.From_env(),
            self.fake_services,  # type: ignore
            self.tuntap_cls,
            self.fake_ws_cls,  # type: ignore
        )

        asyncio.create_task(_helper_stop_instance(server_instance))
        await server_instance
