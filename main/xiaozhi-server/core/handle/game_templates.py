"""
游戏模板：出题器 + 判题器 + 题库 + 话术模板
每个游戏实现 BaseGame 接口，只替换出题和判题逻辑
"""

import random
import re
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Any, List


class BaseGame(ABC):
    """游戏基类接口"""

    @abstractmethod
    def get_opening(self) -> str:
        """返回游戏开场白"""
        pass

    @abstractmethod
    def generate_question(self, round_index: int, consecutive_correct: int, consecutive_wrong: int) -> Tuple[str, Any, int]:
        """生成一道题
        返回: (题目文本, 答案, 超时秒数)
        """
        pass

    @abstractmethod
    def normalize_input(self, text: str) -> str:
        """归一化用户输入（ASR 结果 → 标准格式）"""
        pass

    @abstractmethod
    def check_answer(self, normalized_input: str, answer: Any) -> bool:
        """判断答案是否正确"""
        pass

    @abstractmethod
    def get_hint(self, answer: Any) -> Optional[str]:
        """获取提示"""
        pass

    @abstractmethod
    def format_answer(self, answer: Any) -> str:
        """格式化答案用于播报"""
        pass

    @property
    def advance_on_wrong(self) -> bool:
        """答错时是否推进到下一题。multi-guess 游戏（如数字炸弹）返回 False"""
        return True

    def get_correct_feedback(self, normalized_input: str, answer: Any,
                             consecutive_correct: int, consecutive_wrong: int) -> Optional[str]:
        """自定义答对反馈，返回 None 则使用默认话术"""
        return None

    def get_wrong_feedback(self, normalized_input: str, answer: Any) -> str:
        """答错时的反馈"""
        return random.choice([
            f"差一点点！答案是{self.format_answer(answer)}哦，没关系，下一题继续！",
            f"这题有点难哦，答案是{self.format_answer(answer)}，不要紧！",
            f"没关系！答案是{self.format_answer(answer)}，下一题你肯定能答对！",
        ])

    def on_correct(self, consecutive_correct: int, consecutive_wrong: int):
        """答对后的回调（用于更新内部状态，如难度）"""
        pass

    def on_wrong(self, consecutive_correct: int, consecutive_wrong: int):
        """答错后的回调"""
        pass

    def restore_from_profile(self, profile: dict):
        """从 game_profile 恢复游戏状态（子类按需实现）"""
        pass


# ====== ASR 数字归一化 ======

# 中文数字 → 阿拉伯数字（基础映射）
_CHINESE_NUM_MAP = {
    "零": 0, "〇": 0,
    "一": 1, "幺": 1,
    "二": 2, "两": 2,
    "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10, "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
    "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
    "二十一": 21, "二十二": 22, "二十三": 23, "二十四": 24, "二十五": 25,
    "二十六": 26, "二十七": 27, "二十八": 28, "二十九": 29,
    "三十": 30, "三十一": 31, "三十二": 32, "三十三": 33, "三十四": 34,
    "三十五": 35, "三十六": 36, "三十七": 37, "三十八": 38, "三十九": 39,
    "四十": 40, "四十一": 41, "四十二": 42, "四十三": 43, "四十四": 44,
    "四十五": 45, "四十六": 46, "四十七": 47, "四十八": 48, "四十九": 49,
    "五十": 50,
}

# ASR 常见误识别映射（在口算上下文中）
_ASR_CONFUSION = {
    "吧": "8", "是": "4", "死": "4", "酒": "9", "零": "0",
    "溜": "6", "妻": "7", "爸": "8", "舅": "9", "二三": "23",
}


def normalize_number(text: str) -> Optional[int]:
    """将用户输入归一化为数字
    支持: "8" / "八" / "二十一" / "吧"(ASR误识别) / "二十三"
    """
    text = text.strip()

    # 先尝试直接解析为数字
    try:
        num = int(text)
        if 0 <= num <= 100:
            return num
    except ValueError:
        pass

    # 中文数字直接查表
    if text in _CHINESE_NUM_MAP:
        return _CHINESE_NUM_MAP[text]

    # ASR 误识别修正
    corrected = _ASR_CONFUSION.get(text)
    if corrected:
        try:
            return int(corrected)
        except ValueError:
            pass

    # 尝试从文本中提取数字
    numbers = re.findall(r'\d+', text)
    if numbers:
        try:
            return int(numbers[0])
        except ValueError:
            pass

    # 尝试组合中文数字（如 "三十二"）
    for cn_num in sorted(_CHINESE_NUM_MAP.keys(), key=len, reverse=True):
        if cn_num in text:
            return _CHINESE_NUM_MAP[cn_num]

    return None


def _decompose_addition(a: int, b: int) -> str:
    """分步提示：拆解加法（凑十法）
    例如 27+8 → "27 加 3 先到 30，再加 5 就好啦"
    """
    if a + b <= 20:
        return f"试试看，{a} 加 {b} 等于多少呢？"

    # 找到凑十的数
    to_ten = 10 - (a % 10) if a % 10 != 0 else 0
    if to_ten > 0 and b > to_ten:
        remainder = b - to_ten
        next_ten = a + to_ten
        return f"{a} 加 {to_ten} 先到 {next_ten}，再加 {remainder} 就好啦！"
    else:
        return f"试试把 {a} 拆开，加上 {b} 等于多少呢？"


def _decompose_subtraction(a: int, b: int) -> str:
    """分步提示：拆解减法
    例如 25-8 → "25 减 5 先到 20，再减 3"
    """
    if a - b >= 0 and a - b <= 20:
        return f"试试看，{a} 减 {b} 等于多少呢？"

    # 先减到整十
    to_ten = a % 10
    if to_ten > 0 and b > to_ten:
        remainder = b - to_ten
        prev_ten = a - to_ten
        return f"{a} 减 {to_ten} 先到 {prev_ten}，再减 {remainder} 就好啦！"
    else:
        return f"试试把 {a} 减 {b}，等于多少呢？"


# ====== 数学运算中文表达 ======

def _number_to_chinese(n: int) -> str:
    """数字转中文口语（用于出题）"""
    if 0 <= n <= 50:
        for cn, num in _CHINESE_NUM_MAP.items():
            if num == n:
                return cn
    return str(n)


# ====== 口算闯关游戏 ======

class MathGame(BaseGame):
    """口算闯关：50 以内加减法，3 级难度"""

    DIFFICULTY_LEVELS = {
        1: {"name": "简单", "max_num": 20, "timeout": 20,
            "description": "20以内"},
        2: {"name": "中等", "max_num": 30, "timeout": 30,
            "description": "30以内"},
        3: {"name": "困难", "max_num": 50, "timeout": 45,
            "description": "50以内"},
    }

    def __init__(self):
        self.difficulty = 1  # 从简单开始
        self._last_a = 0
        self._last_b = 0
        self._last_op = "+"

    def get_opening(self) -> str:
        if self.difficulty > 1:
            level_name = self.DIFFICULTY_LEVELS[self.difficulty]["description"]
            return f"口算闯关开始啦！上次你很厉害，这次从{level_name}开始，准备好了吗？"
        return "口算闯关开始啦！先从简单的来，准备好了吗？"

    def restore_from_profile(self, profile: dict):
        """从 game_profile 恢复难度设置"""
        stable = profile.get("stable_difficulty")
        if stable and isinstance(stable, int) and 1 <= stable <= 3:
            self.difficulty = stable

    def generate_question(self, round_index: int, consecutive_correct: int, consecutive_wrong: int) -> Tuple[str, Any, int]:
        """生成一道口算题
        返回: (题目文本, 答案数字, 超时秒数)
        """
        level = self.DIFFICULTY_LEVELS[self.difficulty]
        max_num = level["max_num"]
        timeout = level["timeout"]

        # 随机选择加法或减法
        op = random.choice(["+", "-"])

        if op == "+":
            a = random.randint(1, max_num)
            b = random.randint(1, max_num - a) if max_num - a > 0 else random.randint(1, 5)
            answer = a + b

            # 中等和困难优先出进位题
            if self.difficulty >= 2 and random.random() < 0.7:
                # 让个位相加 > 10（进位）
                a_ones = a % 10
                lo = 10 - a_ones
                hi = min(9, max_num - a)
                if lo <= hi:  # 边界保护
                    b = random.randint(lo, hi)
                    answer = a + b
        else:
            # 减法：保证结果 >= 0
            a = random.randint(1, max_num)
            b = random.randint(1, a)
            answer = a - b

            # 中等和困难优先出退位题
            if self.difficulty >= 2 and random.random() < 0.7:
                a_ones = a % 10
                lo = a_ones + 1
                hi = min(a_ones + 9, a)
                if lo <= hi:  # 边界保护
                    b = random.randint(lo, hi)
                    answer = a - b

        # 避免和上一题完全相同（循环重试，不用递归）
        if a == self._last_a and b == self._last_b and op == self._last_op:
            # 简单交换 a, b 或重选 op
            if op == "+" and a != b:
                a, b = b, a
                answer = a + b
            else:
                op = "-" if op == "+" else "+"
                if op == "-":
                    a, b = max(a, b), min(a, b)
                    answer = a - b
                else:
                    answer = a + b

        self._last_a = a
        self._last_b = b
        self._last_op = op

        # 中文口语出题
        op_str = "加" if op == "+" else "减"
        a_cn = _number_to_chinese(a)
        b_cn = _number_to_chinese(b)

        question = f"{a_cn}{op_str}{b_cn}等于几呢？"
        return question, answer, timeout

    def normalize_input(self, text: str) -> str:
        """归一化用户输入"""
        return text.strip()

    def check_answer(self, normalized_input: str, answer: Any) -> bool:
        """判断答案"""
        user_num = normalize_number(normalized_input)
        if user_num is None:
            return False
        return user_num == answer

    def get_hint(self, answer: Any) -> Optional[str]:
        """分步提示"""
        a, b, op = self._last_a, self._last_b, self._last_op
        if op == "+":
            return _decompose_addition(a, b)
        else:
            return _decompose_subtraction(a, b)

    def format_answer(self, answer: Any) -> str:
        """格式化答案"""
        return _number_to_chinese(answer)

    def on_correct(self, consecutive_correct: int, consecutive_wrong: int):
        """答对后，连对 2 题升级"""
        if consecutive_correct >= 2 and self.difficulty < 3:
            self.difficulty += 1

    def on_wrong(self, consecutive_correct: int, consecutive_wrong: int):
        """答错后，连错 2 题降级（悄悄降，不说）"""
        if consecutive_wrong >= 2 and self.difficulty > 1:
            self.difficulty -= 1


# ====== 数字炸弹游戏 ======

class NumberBombGame(BaseGame):
    """数字炸弹：从 1 到 N 猜数字，范围根据表现动态调整

    自适应规则（每轮猜中后调整）：
    - ≤3 次猜中：扩大范围 +10（上限 50）
    - >6 次猜中：缩小范围 -10（下限 10）
    - 其他：保持当前范围
    """

    MIN_RANGE = 10      # 最小范围上限
    MAX_RANGE = 50      # 最大范围上限
    START_RANGE = 20    # 初始范围上限
    RANGE_STEP = 10     # 每次调整步长
    RANGE_UP_THRESHOLD = 3    # ≤ 此次数猜中则升级
    RANGE_DOWN_THRESHOLD = 6  # > 此次数猜中则降级

    def __init__(self):
        self._secret = 0
        self._guesses_this_round = 0
        self._last_guess = 0
        self._max_number = self.START_RANGE  # 当前范围上限（动态）
        self._prev_max_number = self.START_RANGE  # 上轮范围（用于开场提示变化）

    @property
    def advance_on_wrong(self) -> bool:
        return False  # multi-guess: wrong answer stays on same question

    def get_opening(self) -> str:
        if self._max_number > self.START_RANGE:
            return f"数字炸弹来啦！上次你很厉害，这次从1到{self._max_number}，准备好了吗？"
        return f"数字炸弹来啦！1到{self._max_number}，我来想一个数字，你来猜！"

    def restore_from_profile(self, profile: dict):
        """从 game_profile 恢复范围设置"""
        stable = profile.get("stable_difficulty")
        if stable and isinstance(stable, int):
            self._max_number = max(self.MIN_RANGE, min(self.MAX_RANGE, stable))
            self._prev_max_number = self._max_number

    def generate_question(self, round_index: int, consecutive_correct: int,
                          consecutive_wrong: int) -> Tuple[str, Any, int]:
        self._secret = random.randint(1, self._max_number)
        self._guesses_this_round = 0
        self._last_guess = 0
        return f"1到{self._max_number}，你猜是多少？", self._secret, 30

    def normalize_input(self, text: str) -> str:
        return text.strip()

    def check_answer(self, normalized_input: str, answer: Any) -> bool:
        num = normalize_number(normalized_input)
        if num is None:
            return False
        self._last_guess = num
        self._guesses_this_round += 1
        return num == answer

    def get_hint(self, answer: Any) -> Optional[str]:
        if self._last_guess and self._last_guess != answer:
            if self._last_guess < answer:
                return f"比{self._last_guess}大哦，再试试！"
            else:
                return f"比{self._last_guess}小哦，再试试！"
        return None

    def format_answer(self, answer: Any) -> str:
        return str(answer)

    def get_wrong_feedback(self, normalized_input: str, answer: Any) -> str:
        num = normalize_number(normalized_input)
        if num is None:
            return "嗯…我没听清你说的数字，再说一次好不好？"
        if num < answer:
            return random.choice([
                "小了小了，往大的猜！",
                "太小啦！试试大一点的数～",
                "不够大哦，再猜！",
            ])
        else:
            return random.choice([
                "大了大了，往小的猜！",
                "太大啦！试试小一点的数～",
                "太大了哦，再猜！",
            ])

    def get_correct_feedback(self, normalized_input: str, answer: Any,
                             consecutive_correct: int, consecutive_wrong: int) -> Optional[str]:
        guesses = self._guesses_this_round
        range_changed = self._max_number != self._prev_max_number

        # 基础反馈
        if guesses == 1:
            base = "哇！一次就猜中！你是神算子吗？"
        elif guesses <= 3:
            base = f"答对啦！用了{guesses}次就猜中了，真厉害！"
        elif guesses <= 6:
            base = f"终于猜中啦！答案是{answer}，用了{guesses}次。"
        else:
            base = f"猜中啦！答案是{answer}，用了{guesses}次。"

        # 范围变化提示
        if range_changed:
            if self._max_number > self._prev_max_number:
                base += f" 下一轮升级！范围扩大到1到{self._max_number}咯～"
            else:
                base += " 下一轮范围缩小了点，更简单啦～"

        return base

    def on_correct(self, consecutive_correct: int, consecutive_wrong: int):
        """根据本轮猜测次数调整范围"""
        self._prev_max_number = self._max_number
        if self._guesses_this_round <= self.RANGE_UP_THRESHOLD:
            self._max_number = min(self.MAX_RANGE, self._max_number + self.RANGE_STEP)
        elif self._guesses_this_round > self.RANGE_DOWN_THRESHOLD:
            self._max_number = max(self.MIN_RANGE, self._max_number - self.RANGE_STEP)

    def on_wrong(self, consecutive_correct: int, consecutive_wrong: int):
        pass


# ====== 游戏类型注册表 ======

GAME_REGISTRY = {
    "math": {
        "class": MathGame,
        "keywords": ["口算", "算数", "算术", "数学", "加减法", "玩数学", "玩口算", "算数游戏"],
        "name": "口算闯关",
    },
    "number_bomb": {
        "class": NumberBombGame,
        "keywords": ["数字炸弹", "猜数字", "数字游戏", "炸弹", "猜数", "猜数字游戏"],
        "name": "数字炸弹",
    },
    # "minecraft_quiz" 和 "riddle" 由各自的模块注册
}


def create_game(game_type: str) -> Optional[BaseGame]:
    """根据类型创建游戏实例"""
    if game_type in GAME_REGISTRY:
        return GAME_REGISTRY[game_type]["class"]()
    return None


def find_game_by_keyword(text: str) -> Optional[str]:
    """根据用户输入匹配游戏类型
    返回游戏类型字符串，或 None
    """
    for game_type, config in GAME_REGISTRY.items():
        for kw in config["keywords"]:
            if kw in text:
                return game_type
    return None
