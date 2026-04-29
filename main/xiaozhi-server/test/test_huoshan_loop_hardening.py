import asyncio
import concurrent.futures
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.connection import ConnectionHandler
from core.providers.tts.huoshan_double_stream import TTSProvider


class QueryMemoryTimeoutTests(unittest.TestCase):
    def test_query_memory_timeout_falls_back_to_empty_string(self):
        handler = object.__new__(ConnectionHandler)
        handler.memory = Mock()
        handler.memory.query_memory.return_value = object()
        handler.loop = object()
        handler.logger = Mock()

        future = Mock()
        future.result.side_effect = concurrent.futures.TimeoutError()

        with patch("core.connection.asyncio.run_coroutine_threadsafe", return_value=future):
            result = handler._query_memory_with_timeout("hello", timeout=3)

        self.assertEqual(result, "")


class HuoshanStartSessionYieldTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_session_yields_once_before_ensure_connection(self):
        provider = object.__new__(TTSProvider)
        provider.activate_session = False
        provider.ws = object()
        provider.voice = "voice"
        provider.close = AsyncMock()
        provider.send_event = AsyncMock()
        provider.get_payload_bytes = Mock(return_value=b"{}")

        call_order = []

        async def fake_sleep(delay):
            call_order.append(("sleep", delay))

        async def fake_ensure_connection():
            call_order.append(("ensure_connection", None))

        provider._ensure_connection = fake_ensure_connection

        with patch("core.providers.tts.huoshan_double_stream.asyncio.sleep", side_effect=fake_sleep):
            await provider.start_session("session-1")

        self.assertGreaterEqual(len(call_order), 2)
        self.assertEqual(call_order[0], ("sleep", 0))
        self.assertEqual(call_order[1], ("ensure_connection", None))


if __name__ == "__main__":
    unittest.main()
