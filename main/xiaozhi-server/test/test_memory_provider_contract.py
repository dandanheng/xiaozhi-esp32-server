import sys
import types
import unittest

logger_stub = types.ModuleType("config.logger")


class _FakeLogger:
    def bind(self, **kwargs):
        return self

    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


logger_stub.setup_logging = lambda: _FakeLogger()
sys.modules.setdefault("config.logger", logger_stub)

from core.providers.memory.nomem.nomem import MemoryProvider as NoMemProvider
from core.providers.memory.mem_report_only.mem_report_only import (
    MemoryProvider as ReportOnlyProvider,
)


class MemoryProviderContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_nomem_query_memory_accepts_scene_kwargs(self):
        provider = NoMemProvider(config={})

        result = await provider.query_memory(
            "玩口算", scene="game", game_type="math"
        )

        self.assertEqual(result, "")

    async def test_report_only_query_memory_accepts_scene_kwargs(self):
        provider = ReportOnlyProvider(config={})

        result = await provider.query_memory(
            "玩我的世界", scene="game", game_type="minecraft_quiz"
        )

        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
