from ..base import MemoryProviderBase, logger
import time
import json
import os
import yaml
from config.config_loader import get_project_dir
from config.manage_api_client import generate_and_save_chat_summary
from core.utils.util import check_model_key


short_term_memory_prompt = """
# 儿童陪伴记忆整理器

你的任务是根据最近对话，整理出适合儿童语音陪伴场景的短期画像。
只保留对后续互动真正有帮助的信息，不要写成人职场、泛社交、长篇推理类内容。

## 记录重点
1. 兴趣偏好：孩子最近喜欢的话题、角色、游戏、动物、故事类型
2. 互动模式：更喜欢聊天、问答、小游戏、被给选项、还是被鼓励
3. 情绪线索：什么会让孩子开心、沮丧、害怕、兴奋
4. 有效引导：哪些说法、风格、节奏更容易接住他

## 不要记录
- 逐题的游戏过程
- 无意义的寒暄
- 模型自己的推测
- 不确定且没有证据的判断

## 输出要求
- 只输出可解析 JSON
- 不要解释、不要 markdown、不要代码块
- 如果没有信息，就给空数组或空字符串

{
  "兴趣偏好": {
    "喜欢话题": [],
    "喜欢游戏": [],
    "喜欢角色或元素": []
  },
  "互动模式": {
    "偏好互动": [],
    "有效引导方式": [],
    "注意力特征": ""
  },
  "情绪线索": {
    "开心触发点": [],
    "沮丧触发点": [],
    "安抚方式": []
  },
  "近期变化": [],
  "待跟进": []
}
"""


def extract_json_data(json_code):
    start = json_code.find("```json")
    end = json_code.find("```", start + 1)
    if start == -1 or end == -1:
        try:
            json.loads(json_code)
            return json_code
        except Exception as e:
            print("Error:", e)
        return ""
    return json_code[start + 7: end]


TAG = __name__


class MemoryProvider(MemoryProviderBase):
    def __init__(self, config, summary_memory):
        super().__init__(config)
        self.short_memory = ""
        self.memory_record = self._empty_memory_record()
        self.save_to_file = True
        self.memory_path = get_project_dir() + "data/.memory.yaml"
        self.load_memory(summary_memory)

    @staticmethod
    def _empty_memory_record():
        return {
            "profile_summary": "",
            "game_profile": {},
        }

    def _normalize_memory_record(self, raw_memory):
        record = self._empty_memory_record()

        if raw_memory is None:
            return record

        if isinstance(raw_memory, dict) and (
            "profile_summary" in raw_memory or "game_profile" in raw_memory
        ):
            profile_summary = raw_memory.get("profile_summary", "")
            if isinstance(profile_summary, dict):
                profile_summary = json.dumps(profile_summary, ensure_ascii=False)
            elif profile_summary is None:
                profile_summary = ""
            record["profile_summary"] = profile_summary
            record["game_profile"] = raw_memory.get("game_profile", {}) or {}
            return record

        if isinstance(raw_memory, str):
            record["profile_summary"] = raw_memory
            return record

        if isinstance(raw_memory, dict):
            record["profile_summary"] = json.dumps(raw_memory, ensure_ascii=False)
            return record

        record["profile_summary"] = str(raw_memory)
        return record

    def _set_memory_record(self, record):
        self.memory_record = self._normalize_memory_record(record)
        self.short_memory = self.memory_record["profile_summary"]

    def init_memory(
        self, role_id, llm, summary_memory=None, save_to_file=True, **kwargs
    ):
        super().init_memory(role_id, llm, **kwargs)
        self.save_to_file = save_to_file
        self.load_memory(summary_memory)

    def load_memory(self, summary_memory):
        if summary_memory or not self.save_to_file:
            self._set_memory_record(summary_memory)
            return

        all_memory = {}
        if os.path.exists(self.memory_path):
            with open(self.memory_path, "r", encoding="utf-8") as f:
                all_memory = yaml.safe_load(f) or {}
        self._set_memory_record(all_memory.get(self.role_id))

    def save_memory_to_file(self):
        all_memory = {}
        if os.path.exists(self.memory_path):
            with open(self.memory_path, "r", encoding="utf-8") as f:
                all_memory = yaml.safe_load(f) or {}
        all_memory[self.role_id] = self.memory_record
        with open(self.memory_path, "w", encoding="utf-8") as f:
            yaml.dump(all_memory, f, allow_unicode=True)

    def get_game_profile(self, game_type=None):
        game_profile = self.memory_record.get("game_profile", {}) or {}
        if game_type:
            return game_profile.get(game_type, {})
        return game_profile

    def set_game_profile(self, game_profile, game_type=None, persist=True):
        current_game_profile = self.memory_record.get("game_profile", {}) or {}
        if game_type:
            current_game_profile[game_type] = game_profile
        else:
            current_game_profile = game_profile or {}
        self.memory_record["game_profile"] = current_game_profile
        if persist and self.save_to_file:
            self.save_memory_to_file()

    async def save_memory(self, msgs, session_id=None):
        model_info = getattr(self.llm, "model_name", str(self.llm.__class__.__name__))
        logger.bind(tag=TAG).debug(f"使用记忆保存模型: {model_info}")
        api_key = getattr(self.llm, "api_key", None)
        memory_key_msg = check_model_key("记忆总结专用LLM", api_key)
        if memory_key_msg:
            logger.bind(tag=TAG).error(memory_key_msg)
        if self.llm is None:
            logger.bind(tag=TAG).error("LLM is not set for memory provider")
            return None

        if len(msgs) < 2:
            return None

        msg_str = ""
        for msg in msgs:
            content = msg.content

            try:
                if (
                    content
                    and content.strip().startswith("{")
                    and content.strip().endswith("}")
                ):
                    data = json.loads(content)
                    if "content" in data:
                        content = data["content"]
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

            if msg.role == "user":
                msg_str += f"User: {content}\n"
            elif msg.role == "assistant":
                msg_str += f"Assistant: {content}\n"

        if self.short_memory:
            msg_str += "历史记忆：\n"
            msg_str += self.short_memory

        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        msg_str += f"当前时间：{time_str}"

        if self.save_to_file:
            try:
                result = self.llm.response_no_stream(
                    short_term_memory_prompt,
                    msg_str,
                    max_tokens=2000,
                    temperature=0.2,
                )
                json_str = extract_json_data(result)
                json.loads(json_str)
                self.memory_record["profile_summary"] = json_str
                self.short_memory = json_str
                self.save_memory_to_file()
            except Exception as e:
                logger.bind(tag=TAG).error(f"Error in saving memory: {e}")
        else:
            summary_id = session_id if session_id else self.role_id
            await generate_and_save_chat_summary(summary_id)

        logger.bind(tag=TAG).info(
            f"Save memory successful - Role: {self.role_id}, Session: {session_id}"
        )
        return self.short_memory

    async def query_memory(self, query: str, scene: str = "chat", game_type=None) -> str:
        if scene == "game":
            return json.dumps(self.get_game_profile(game_type), ensure_ascii=False)
        if scene == "all":
            return json.dumps(self.memory_record, ensure_ascii=False)
        return self.memory_record.get("profile_summary", "")
