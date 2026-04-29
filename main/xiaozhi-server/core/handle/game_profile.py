"""
游戏画像持久化：读写 game_profile 到 mem_local_short
与 LLM 记忆总结完全独立，直接操作结构化数据
"""

import yaml
import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

TAG = __name__


def get_memory_file_path(conn) -> str:
    """获取 .memory.yaml 文件路径"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '.memory.yaml')


def save_game_profile(conn, game_type: str, stats: Dict[str, Any]):
    """游戏结束后保存画像到 game_profile

    Args:
        conn: 连接对象，需要 conn.memory (MemoryProvider) 和 conn.headers (含 device_id)
        game_type: 游戏类型 ("math", "minecraft_quiz" 等)
        stats: 游戏统计数据
    """
    try:
        if not hasattr(conn, 'memory') or conn.memory is None:
            conn.logger.bind(tag=TAG).warning("记忆服务未初始化，跳过游戏画像保存")
            return

        provider = conn.memory
        if not hasattr(provider, 'get_game_profile'):
            conn.logger.bind(tag=TAG).warning("记忆服务不支持 game_profile，跳过")
            return

        # 读取当前画像
        current = provider.get_game_profile(game_type) or {}

        # 累加统计
        current["total_games"] = current.get("total_games", 0) + 1
        current["total_correct"] = current.get("total_correct", 0) + stats.get("correct_count", 0)
        current["total_questions"] = current.get("total_questions", 0) + stats.get("round_index", 0)
        current["last_played"] = datetime.now().strftime("%Y-%m-%d")

        # 口算 / 数字炸弹：稳定难度
        if game_type in ("math", "number_bomb") and "difficulty" in stats:
            current["stable_difficulty"] = stats["difficulty"]

        # Minecraft 特有：弱项分类
        if game_type == "minecraft_quiz" and "wrong_categories" in stats:
            existing = current.get("weak_categories", [])
            for cat in stats["wrong_categories"]:
                if cat not in existing:
                    existing.append(cat)
            # 只保留最近 5 个弱项
            current["weak_categories"] = existing[-5:]

        # 保存
        provider.set_game_profile(current, game_type=game_type, persist=True)
        conn.logger.bind(tag=TAG).info(f"游戏画像已保存: {game_type} -> {current}")

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"保存游戏画像失败: {e}")


def load_game_profile(conn, game_type: str) -> Dict[str, Any]:
    """游戏启动时读取画像

    Args:
        conn: 连接对象
        game_type: 游戏类型

    Returns:
        该游戏的画像数据，如果没有则返回空 dict
    """
    try:
        if not hasattr(conn, 'memory') or conn.memory is None:
            return {}

        provider = conn.memory
        if not hasattr(provider, 'get_game_profile'):
            return {}

        return provider.get_game_profile(game_type) or {}

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"读取游戏画像失败: {e}")
        return {}
