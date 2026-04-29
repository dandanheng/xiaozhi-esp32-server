import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock

import yaml

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

config_loader_stub = types.ModuleType("config.config_loader")
config_loader_stub.get_project_dir = lambda: ""

manage_api_client_stub = types.ModuleType("config.manage_api_client")


async def _fake_generate_and_save_chat_summary(session_id):
    return None


manage_api_client_stub.generate_and_save_chat_summary = _fake_generate_and_save_chat_summary

util_stub = types.ModuleType("core.utils.util")
util_stub.check_model_key = lambda model_type, model_key: None

sys.modules.setdefault("config.logger", logger_stub)
sys.modules.setdefault("config.config_loader", config_loader_stub)
sys.modules.setdefault("config.manage_api_client", manage_api_client_stub)
sys.modules.setdefault("core.utils.util", util_stub)

from core.providers.memory.mem_local_short import mem_local_short
from core.providers.memory.mem_local_short.mem_local_short import MemoryProvider


class MemLocalShortTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_dir = self.tempdir.name + "/"
        os.makedirs(os.path.join(self.project_dir, "data"), exist_ok=True)
        self.memory_path = os.path.join(self.project_dir, "data", ".memory.yaml")
        mem_local_short.get_project_dir = lambda: self.project_dir

    def tearDown(self):
        self.tempdir.cleanup()

    def _create_provider(self, role_id="device-1"):
        provider = MemoryProvider(config={}, summary_memory=None)
        provider.role_id = role_id
        provider.load_memory(summary_memory=None)
        return provider

    def test_load_memory_migrates_legacy_string_record(self):
        legacy_summary = json.dumps({"兴趣偏好": {"喜欢话题": ["Minecraft"]}}, ensure_ascii=False)
        with open(self.memory_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"device-1": legacy_summary}, f, allow_unicode=True)

        provider = self._create_provider()
        provider.load_memory(summary_memory=None)

        self.assertEqual(provider.short_memory, legacy_summary)
        self.assertEqual(provider.memory_record["profile_summary"], legacy_summary)
        self.assertEqual(provider.memory_record["game_profile"], {})

    async def test_save_memory_preserves_game_profile_under_new_schema(self):
        existing_record = {
            "profile_summary": json.dumps({"兴趣偏好": {"喜欢话题": ["恐龙"]}}, ensure_ascii=False),
            "game_profile": {
                "math": {
                    "stable_difficulty": 2,
                }
            },
        }
        with open(self.memory_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"device-1": existing_record}, f, allow_unicode=True)

        provider = self._create_provider()
        provider.llm = Mock()
        provider.llm.model_name = "fake-model"
        provider.llm.api_key = "test-key"
        new_summary = json.dumps({"兴趣偏好": {"喜欢话题": ["Minecraft"]}}, ensure_ascii=False)
        provider.llm.response_no_stream.return_value = new_summary

        msgs = [
            types.SimpleNamespace(role="user", content="我喜欢玩我的世界"),
            types.SimpleNamespace(role="assistant", content="好呀，我们来聊 Minecraft"),
        ]

        await provider.save_memory(msgs)

        with open(self.memory_path, "r", encoding="utf-8") as f:
            stored = yaml.safe_load(f)

        self.assertEqual(stored["device-1"]["profile_summary"], new_summary)
        self.assertEqual(
            stored["device-1"]["game_profile"]["math"]["stable_difficulty"], 2
        )

    async def test_query_memory_supports_scene_filtering(self):
        provider = self._create_provider()
        provider.memory_record = {
            "profile_summary": json.dumps({"兴趣偏好": {"喜欢话题": ["Minecraft"]}}, ensure_ascii=False),
            "game_profile": {
                "math": {"stable_difficulty": 1},
                "minecraft_quiz": {"weak_categories": ["合成"]},
            },
        }
        provider.short_memory = provider.memory_record["profile_summary"]

        chat_memory = await provider.query_memory("聊聊天")
        math_memory = await provider.query_memory("玩口算", scene="game", game_type="math")

        self.assertIn("Minecraft", chat_memory)
        self.assertNotIn("stable_difficulty", chat_memory)
        self.assertIn("stable_difficulty", math_memory)
        self.assertNotIn("Minecraft", math_memory)


if __name__ == "__main__":
    unittest.main()
