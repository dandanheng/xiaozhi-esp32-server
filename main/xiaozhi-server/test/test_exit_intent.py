import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.modules.setdefault("opuslib_next", types.SimpleNamespace())
hello_handle_stub = types.ModuleType("core.handle.helloHandle")
logger_stub = types.ModuleType("config.logger")


class _FakeLogger:
    def bind(self, **kwargs):
        return self

    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


logger_stub.setup_logging = lambda: _FakeLogger()


async def _fake_check_wakeup_words(conn, text):
    return False


hello_handle_stub.checkWakeupWords = _fake_check_wakeup_words
sys.modules.setdefault("config.logger", logger_stub)
sys.modules.setdefault("core.handle.helloHandle", hello_handle_stub)

from core.handle.intentHandler import check_direct_exit
from plugins_func.functions.handle_exit_intent import (
    FIXED_EXIT_RESPONSE,
    handle_exit_intent,
)
from plugins_func.register import Action


class HandleExitIntentTests(unittest.TestCase):
    def test_handle_exit_intent_always_returns_fixed_goodbye(self):
        conn = Mock()
        conn.is_exiting = False
        conn.close_after_chat = False

        result = handle_exit_intent(conn, say_goodbye="模型生成的告别语")

        self.assertTrue(conn.is_exiting)
        self.assertTrue(conn.close_after_chat)
        self.assertEqual(result.action, Action.RESPONSE)
        self.assertEqual(result.response, FIXED_EXIT_RESPONSE)


class CheckDirectExitTests(unittest.IsolatedAsyncioTestCase):
    async def test_check_direct_exit_replies_with_fixed_goodbye(self):
        conn = Mock()
        conn.cmd_exit = ["再见", "退出"]
        conn.logger = Mock()
        conn.is_exiting = False
        conn.close_after_chat = False
        conn.sentence_id = None

        with (
            patch("core.handle.intentHandler.send_stt_message", new=AsyncMock()) as send_stt_message,
            patch("core.handle.intentHandler.speak_txt") as speak_txt,
            patch("core.handle.intentHandler.uuid.uuid4") as uuid4_mock,
        ):
            uuid4_mock.return_value.hex = "exit-sentence-id"

            handled = await check_direct_exit(conn, "再见")

        self.assertTrue(handled)
        self.assertTrue(conn.is_exiting)
        self.assertTrue(conn.close_after_chat)
        self.assertEqual(conn.sentence_id, "exit-sentence-id")
        send_stt_message.assert_awaited_once_with(conn, "再见")
        speak_txt.assert_called_once_with(conn, FIXED_EXIT_RESPONSE)


if __name__ == "__main__":
    unittest.main()
