"""
游戏会话统一状态机
管理游戏生命周期：start → ask → wait_answer → judge → feedback → next/finish
支持全局中断/退出/超时
"""

import time
import random
from typing import Optional, Dict, Any, Tuple
from enum import Enum


class GameState(Enum):
    IDLE = "idle"           # 未在游戏中
    ASKING = "asking"       # 正在出题
    WAITING = "waiting"     # 等待回答
    FINISHED = "finished"   # 游戏结束


# 全局退出/中断关键词
EXIT_KEYWORDS = ["不玩了", "不玩", "退出", "结束游戏", "停", "停止", "不做了"]
SWITCH_KEYWORDS = ["换一个", "换一题", "下一个", "跳过", "换游戏", "不要这个"]

# 鼓励话术
CORRECT_RESPONSES = [
    "答对啦！太棒了！",
    "厉害！答对了！",
    "没错！你真聪明！",
    "对对对！你太厉害了！",
    "完全正确！继续加油！",
]

STREAK_RESPONSES = {
    3: "三连击！你是小达人！",
    5: "五连击！太厉害了！简直是天才！",
}

WRONG_RESPONSES = [
    "差一点点！没关系，下一题继续！",
    "这题有点难哦，没关系！",
    "不要紧！下一题你肯定能答对！",
]

FINISH_RESPONSES = [
    "游戏结束啦！你答对了{correct}题，总共{total}题，真厉害！",
    "闯关完成！{correct}题答对了！你太棒了！",
]


class GameSession:
    """统一游戏会话状态机"""

    def __init__(self):
        self.state = GameState.IDLE
        self.game = None          # 当前游戏实例（MathGame / MinecraftQuiz 等）
        self.game_type = None     # "math" / "minecraft_quiz" / "riddle"
        self.round_index = 0      # 当前第几题（从 0 开始）
        self.total_rounds = 5     # 总题数
        self.correct_count = 0    # 答对几题
        self.consecutive_correct = 0  # 连续答对数
        self.consecutive_wrong = 0    # 连续答错数
        self.current_answer = None    # 当前题目答案
        self.ask_time = 0            # 出题时间戳
        self.timeout_seconds = 30    # 当前题目超时时间
        self.hint_given = False      # 是否已给过提示
        self.last_question_text = ""  # 上一题的题目文本（避免重复）

    @property
    def is_active(self) -> bool:
        return self.state in (GameState.ASKING, GameState.WAITING)

    def start(self, game_type: str, game, total_rounds: int = 5) -> str:
        """启动游戏，返回开场白"""
        self.state = GameState.ASKING
        self.game = game
        self.game_type = game_type
        self.round_index = 0
        self.total_rounds = total_rounds
        self.correct_count = 0
        self.consecutive_correct = 0
        self.consecutive_wrong = 0

        opening = self.game.get_opening()
        return opening

    def next_question(self) -> Optional[str]:
        """生成下一题，返回题目文本。如果没有更多题目，返回 None"""
        if self.round_index >= self.total_rounds:
            return None

        question_text, answer, timeout = self.game.generate_question(
            self.round_index,
            self.consecutive_correct,
            self.consecutive_wrong
        )

        # 避免和上一题完全相同
        if question_text == self.last_question_text:
            question_text, answer, timeout = self.game.generate_question(
                self.round_index,
                self.consecutive_correct,
                self.consecutive_wrong
            )

        self.current_answer = answer
        self.timeout_seconds = timeout
        self.ask_time = time.time()
        self.hint_given = False
        self.state = GameState.WAITING
        self.last_question_text = question_text
        self.round_index += 1

        return question_text

    def judge_answer(self, user_text: str) -> Tuple[bool, str]:
        """判断答案，返回 (是否正确, 反馈文本)"""
        if not self.is_active:
            return False, ""

        normalized = self.game.normalize_input(user_text)
        is_correct = self.game.check_answer(normalized, self.current_answer)

        if is_correct:
            self.correct_count += 1
            self.consecutive_correct += 1
            self.consecutive_wrong = 0

            # 使用游戏自定义答对反馈（如数字炸弹的"用了X次猜中"）
            custom_feedback = self.game.get_correct_feedback(
                normalized, self.current_answer,
                self.consecutive_correct, self.consecutive_wrong
            )
            if custom_feedback:
                feedback = custom_feedback
            else:
                # 连击彩蛋
                streak_msg = ""
                if self.consecutive_correct in STREAK_RESPONSES:
                    streak_msg = STREAK_RESPONSES[self.consecutive_correct]

                # 全对检测
                if self.round_index >= self.total_rounds and self.correct_count == self.total_rounds:
                    feedback = "全部答对！满分通关！你太厉害了！"
                else:
                    feedback = random.choice(CORRECT_RESPONSES)
                    if streak_msg:
                        feedback = streak_msg

            # 让游戏实例也处理一下（比如更新难度）
            self.game.on_correct(self.consecutive_correct, self.consecutive_wrong)
            self.state = GameState.ASKING
        else:
            self.consecutive_correct = 0
            self.consecutive_wrong += 1
            feedback = self.game.get_wrong_feedback(normalized, self.current_answer)

            self.game.on_wrong(self.consecutive_correct, self.consecutive_wrong)

            # Multi-guess 游戏（如数字炸弹）：答错时留在当前题目
            if hasattr(self.game, 'advance_on_wrong') and not self.game.advance_on_wrong:
                pass  # Stay in WAITING, don't advance
            else:
                self.state = GameState.ASKING

        return is_correct, feedback

    def get_hint(self) -> Optional[str]:
        """获取当前题目的提示"""
        if not self.is_active or self.hint_given:
            return None
        self.hint_given = True
        return self.game.get_hint(self.current_answer)

    def check_timeout(self) -> Optional[str]:
        """检查是否超时，返回超时提示或 None"""
        if not self.is_active:
            return None

        elapsed = time.time() - self.ask_time
        if not self.hint_given and elapsed > self.timeout_seconds * 0.6:
            # 过半时间，给提示
            hint = self.get_hint()
            if hint:
                return f"不着急慢慢想哦～{hint}"
            return "不着急慢慢想哦～"

        if elapsed > self.timeout_seconds:
            # 超时，跳过这题
            self.consecutive_correct = 0
            self.consecutive_wrong += 1
            self.state = GameState.ASKING
            answer_text = self.game.format_answer(self.current_answer)
            self.game.on_wrong(self.consecutive_correct, self.consecutive_wrong)
            return f"时间到啦！这道题的答案是{answer_text}，下一题继续加油！"

        return None

    def handle_interrupt(self, text: str) -> Tuple[bool, Optional[str]]:
        """处理中断/退出/换题。返回 (是否处理了, 回复文本)"""
        # 检查退出
        for kw in EXIT_KEYWORDS:
            if kw in text:
                result = self.finish(force=True)
                return True, result

        # 检查换题/跳过
        for kw in SWITCH_KEYWORDS:
            if kw in text:
                if self.is_active:
                    self.consecutive_correct = 0
                    self.state = GameState.ASKING
                    return True, "好，跳过这题！下一题来咯～"
                return True, None

        return False, None

    def finish(self, force: bool = False) -> str:
        """结束游戏，返回结束语"""
        correct = self.correct_count
        total = self.round_index

        self.state = GameState.FINISHED

        if force and total < 2:
            ending = "好的，不玩了！下次再来挑战吧！"
        else:
            template = random.choice(FINISH_RESPONSES)
            ending = template.format(correct=correct, total=total)
            ending += " 想再玩一次吗？"

        # 重置状态
        self.state = GameState.IDLE
        self.game = None
        self.game_type = None

        return ending

    def get_stats(self) -> Dict[str, Any]:
        """获取游戏统计"""
        return {
            "game_type": self.game_type,
            "round_index": self.round_index,
            "total_rounds": self.total_rounds,
            "correct_count": self.correct_count,
            "consecutive_correct": self.consecutive_correct,
            "consecutive_wrong": self.consecutive_wrong,
        }
