import random
import re
from typing import Dict, List, Optional, Tuple

from core.handle.game_templates import BaseGame, GAME_REGISTRY


OPTION_LABELS = ("A", "B", "C")

COMMON_ASR_ALIASES = {
    "铁锭": ["铁定", "铁丁", "铁顶", "贴定", "黑铁力", "铁力"],
    "金锭": ["金定", "金丁", "金顶"],
    "铜锭": ["铜定", "铜丁", "铜顶"],
    "黑曜石": ["黑要石", "黑药石", "黑曜十"],
    "烈焰棒": ["烈焰杖", "烈焰帮", "火焰棒"],
    "末影之眼": ["末影之言", "末影之演", "末影之燕"],
    "红石粉": ["红十粉", "红石分"],
}


def _normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[，。！？、,.!?：:\s]+", "", text)
    return text


def _normalize_option_alias(text: str) -> Optional[str]:
    option_aliases = {
        "A": {"a", "a选项", "选a", "选项a", "第一个", "第一", "第1个", "1", "一"},
        "B": {"b", "b选项", "选b", "选项b", "第二个", "第二", "第2个", "2", "二"},
        "C": {"c", "c选项", "选c", "选项c", "第三个", "第三", "第3个", "3", "三"},
    }
    for label, aliases in option_aliases.items():
        if text in aliases:
            return label
    return None


def _expand_accepted_texts(correct_text: str, aliases: List[str]) -> set:
    accepted = {
        _normalize_text(correct_text),
        *(_normalize_text(alias) for alias in aliases),
    }
    accepted.update(
        _normalize_text(alias)
        for alias in COMMON_ASR_ALIASES.get(correct_text, [])
    )
    return accepted


def _build_question_bank() -> List[Dict]:
    return [
        {
            "id": "mob_creeper_cat",
            "category": "mob",
            "scene": "你在矿洞里听到嘶嘶声，是苦力怕靠近了。",
            "stem": "苦力怕最怕什么动物？",
            "choices": ["猫", "狗", "鸡"],
            "correct_index": 0,
            "aliases": ["猫咪", "豹猫", "小猫"],
            "hint": "提示：是一种毛茸茸、还会喵喵叫的小动物。",
        },
        {
            "id": "mob_enderman_eyes",
            "category": "mob",
            "scene": "你看到一个黑黑高高的怪物站在远处。",
            "stem": "遇到末影人时，最不该做什么？",
            "choices": ["看它的眼睛", "绕开它", "躲远一点"],
            "correct_index": 0,
            "aliases": ["盯着它", "看眼睛"],
            "hint": "提示：有一个动作会让它突然生气。",
        },
        {
            "id": "mob_zombie_sun",
            "category": "mob",
            "scene": "天亮了，僵尸还在外面晃来晃去。",
            "stem": "大部分僵尸在太阳下会怎么样？",
            "choices": ["着火", "变隐身", "跑更快"],
            "correct_index": 0,
            "aliases": ["燃烧", "烧起来"],
            "hint": "提示：白天对它们很不友好。",
        },
        {
            "id": "mob_iron_golem",
            "category": "mob",
            "scene": "你来到一个村庄，看到高大的铁傀儡在巡逻。",
            "stem": "铁傀儡平时主要在保护谁？",
            "choices": ["村民", "苦力怕", "僵尸"],
            "correct_index": 0,
            "aliases": ["村庄的人", "村子里的人"],
            "hint": "提示：它是村庄的守卫。",
        },
        {
            "id": "mob_wolf_tame",
            "category": "mob",
            "scene": "你想在森林里交一个狼朋友。",
            "stem": "驯服狼最常用什么？",
            "choices": ["骨头", "面包", "苹果"],
            "correct_index": 0,
            "aliases": ["骨", "骨骨"],
            "hint": "提示：这是骷髅也会掉落的东西。",
        },
        {
            "id": "mob_cat_tame",
            "category": "mob",
            "scene": "你想把一只小猫带回家。",
            "stem": "驯服猫通常要喂什么？",
            "choices": ["生鳕鱼", "牛奶", "小麦"],
            "correct_index": 0,
            "aliases": ["鱼", "生鱼", "鳕鱼"],
            "hint": "提示：猫最爱吃一种鱼。",
        },
        {
            "id": "mob_spider_day",
            "category": "mob",
            "scene": "白天到了，你看到一只蜘蛛趴在地上。",
            "stem": "普通蜘蛛白天通常会不会主动攻击你？",
            "choices": ["一般不会", "一定会", "只会跳舞"],
            "correct_index": 0,
            "aliases": ["不会", "不太会"],
            "hint": "提示：白天它通常没那么凶。",
        },
        {
            "id": "mob_guardian_home",
            "category": "mob",
            "scene": "你潜到海底深处，看到巨大建筑里有守卫者。",
            "stem": "守卫者一般住在哪种建筑附近？",
            "choices": ["海底神殿", "沙漠神殿", "林地府邸"],
            "correct_index": 0,
            "aliases": ["海底宫殿"],
            "hint": "提示：它在海里，不在沙漠。",
        },
        {
            "id": "mob_dragon_home",
            "category": "mob",
            "scene": "你准备挑战 Minecraft 里的大 Boss。",
            "stem": "末影龙住在哪里？",
            "choices": ["末地", "下界", "主世界海底"],
            "correct_index": 0,
            "aliases": ["末地世界"],
            "hint": "提示：要先找到末地传送门。",
        },
        {
            "id": "mob_bee_attack",
            "category": "mob",
            "scene": "你不小心惹到了一只蜜蜂。",
            "stem": "蜜蜂蛰完人以后通常会怎样？",
            "choices": ["会死掉", "会进化", "会发光"],
            "correct_index": 0,
            "aliases": ["死", "死掉"],
            "hint": "提示：它只能拼一次。",
        },
        {
            "id": "mob_slime_place",
            "category": "mob",
            "scene": "夜里你在一片潮湿的地方蹦来蹦去。",
            "stem": "在什么地形更容易见到史莱姆？",
            "choices": ["沼泽", "沙漠", "雪地"],
            "correct_index": 0,
            "aliases": ["沼泽地"],
            "hint": "提示：这里湿湿的、还有很多水。",
        },
        {
            "id": "mob_witch_from_villager",
            "category": "mob",
            "scene": "一声雷响过后，村庄里发生了怪事。",
            "stem": "村民被闪电劈中后可能变成什么？",
            "choices": ["女巫", "铁傀儡", "苦力怕"],
            "correct_index": 0,
            "aliases": ["巫婆"],
            "hint": "提示：她会扔药水。",
        },
        {
            "id": "mob_enderman_block",
            "category": "mob",
            "scene": "你发现有个怪物总爱搬走家门口的方块。",
            "stem": "哪种怪物最爱搬方块？",
            "choices": ["末影人", "苦力怕", "骷髅"],
            "correct_index": 0,
            "aliases": ["小黑", "高个黑怪"],
            "hint": "提示：它黑黑高高，还会瞬移。",
        },
        {
            "id": "mob_skeleton_close",
            "category": "mob",
            "scene": "骷髅一直在远处朝你射箭。",
            "stem": "对付骷髅射手时，通常更适合靠近还是远离？",
            "choices": ["靠近", "远离", "原地跳"],
            "correct_index": 0,
            "aliases": ["冲上去", "接近"],
            "hint": "提示：别一直给它远程输出的舒服距离。",
        },
        {
            "id": "mob_villager_job",
            "category": "mob",
            "scene": "你在村庄里想找人做交易。",
            "stem": "谁最适合跟你做交易？",
            "choices": ["村民", "僵尸", "蜘蛛"],
            "correct_index": 0,
            "aliases": ["村庄的人"],
            "hint": "提示：它们白天喜欢在村子里走来走去。",
        },
        {
            "id": "craft_table",
            "category": "craft",
            "scene": "你刚砍完树，准备开始真正的生存。",
            "stem": "合成工作台需要几块木板？",
            "choices": ["4块", "2块", "9块"],
            "correct_index": 0,
            "aliases": ["四块", "4"],
            "hint": "提示：是一个 2x2 的正方形。",
        },
        {
            "id": "craft_chest",
            "category": "craft",
            "scene": "你背包快装不下了，准备做个箱子。",
            "stem": "合成箱子需要几块木板？",
            "choices": ["8块", "6块", "4块"],
            "correct_index": 0,
            "aliases": ["八块", "8"],
            "hint": "提示：围一圈，中间空一格。",
        },
        {
            "id": "craft_torch",
            "category": "craft",
            "scene": "矿洞里太黑了，你需要做些火把。",
            "stem": "火把通常是木棍配什么材料做出来的？",
            "choices": ["煤炭", "钻石", "砂砾"],
            "correct_index": 0,
            "aliases": ["煤", "煤块"],
            "hint": "提示：黑黑的，挖煤时就会遇到。",
        },
        {
            "id": "craft_bed_wool",
            "category": "craft",
            "scene": "天快黑了，你想赶紧睡一觉。",
            "stem": "做一张床需要几块羊毛？",
            "choices": ["3块", "1块", "5块"],
            "correct_index": 0,
            "aliases": ["三块", "3"],
            "hint": "提示：上面一排都要用到。",
        },
        {
            "id": "craft_wood_pickaxe",
            "category": "craft",
            "scene": "你要做最基础的工具开始挖矿。",
            "stem": "做一把木镐需要几块木板？",
            "choices": ["3块", "2块", "5块"],
            "correct_index": 0,
            "aliases": ["三块", "3"],
            "hint": "提示：上面一整排。",
        },
        {
            "id": "craft_diamond_sword",
            "category": "craft",
            "scene": "你终于挖到钻石，想做一把武器。",
            "stem": "合成钻石剑需要几颗钻石？",
            "choices": ["2颗", "1颗", "4颗"],
            "correct_index": 0,
            "aliases": ["两颗", "2"],
            "hint": "提示：上面两格是同一种材料。",
        },
        {
            "id": "craft_bucket",
            "category": "craft",
            "scene": "你想把水带回家种田。",
            "stem": "铁桶是用什么材料做的？",
            "choices": ["铁锭", "金锭", "铜锭"],
            "correct_index": 0,
            "aliases": ["铁"],
            "hint": "提示：灰灰亮亮的金属。",
        },
        {
            "id": "craft_shield_center",
            "category": "craft",
            "scene": "你要准备一面盾牌去探险。",
            "stem": "做盾牌时，中间那格通常放什么？",
            "choices": ["铁锭", "钻石", "煤炭"],
            "correct_index": 0,
            "aliases": ["铁"],
            "hint": "提示：是一小块金属材料。",
        },
        {
            "id": "craft_brewing_stand",
            "category": "craft",
            "scene": "你准备开始酿药水了。",
            "stem": "酿造台最关键的特殊材料是什么？",
            "choices": ["烈焰棒", "甘蔗", "青金石"],
            "correct_index": 0,
            "aliases": ["火焰棒"],
            "hint": "提示：它和烈焰人有关。",
        },
        {
            "id": "craft_enchanting_table",
            "category": "craft",
            "scene": "你想给工具附魔，变得更强。",
            "stem": "附魔台需要哪种黑色方块？",
            "choices": ["黑曜石", "煤炭块", "深板岩"],
            "correct_index": 0,
            "aliases": ["黑曜石块"],
            "hint": "提示：它很硬，传送门也要用到。",
        },
        {
            "id": "craft_compass",
            "category": "craft",
            "scene": "你想做个东西帮助自己找到熟悉的位置。",
            "stem": "指南针一般会指向哪里？",
            "choices": ["世界出生点", "最近村庄", "下界入口"],
            "correct_index": 0,
            "aliases": ["出生点", "家里出生点"],
            "hint": "提示：它不是专门找村庄的。",
        },
        {
            "id": "craft_rail",
            "category": "craft",
            "scene": "你准备修一条矿车轨道。",
            "stem": "普通铁轨主要用什么金属做？",
            "choices": ["铁锭", "金锭", "铜锭"],
            "correct_index": 0,
            "aliases": ["铁"],
            "hint": "提示：矿车相关常用这种银灰色金属。",
        },
        {
            "id": "craft_furnace",
            "category": "craft",
            "scene": "你想把生肉烤熟，也想烧矿。",
            "stem": "做熔炉通常要围一圈什么方块？",
            "choices": ["圆石", "泥土", "木板"],
            "correct_index": 0,
            "aliases": ["石头", "圆石块"],
            "hint": "提示：最早期挖到的一种石头方块。",
        },
        {
            "id": "craft_boat",
            "category": "craft",
            "scene": "你准备坐船过河。",
            "stem": "木船通常主要用什么材料做？",
            "choices": ["木板", "羊毛", "铁锭"],
            "correct_index": 0,
            "aliases": ["木头板", "木头"],
            "hint": "提示：和做箱子、工作台同源。",
        },
        {
            "id": "survival_portal_block",
            "category": "survival",
            "scene": "你想去下界冒险，开始搭传送门。",
            "stem": "下界传送门主要用什么方块搭？",
            "choices": ["黑曜石", "铁块", "钻石块"],
            "correct_index": 0,
            "aliases": ["黑曜石块"],
            "hint": "提示：非常硬，通常要用钻石镐挖。",
        },
        {
            "id": "survival_portal_ignite",
            "category": "survival",
            "scene": "传送门已经搭好了，还差最后一步。",
            "stem": "通常用什么点燃下界传送门？",
            "choices": ["打火石", "火把", "红石粉"],
            "correct_index": 0,
            "aliases": ["燧石和铁", "打火器"],
            "hint": "提示：这是一个能生火的小工具。",
        },
        {
            "id": "survival_bed_nether",
            "category": "survival",
            "scene": "你带着床冲进下界，想顺手睡一觉。",
            "stem": "在下界直接睡床会发生什么？",
            "choices": ["床会爆炸", "可以正常睡", "直接传回主世界"],
            "correct_index": 0,
            "aliases": ["爆炸", "炸了"],
            "hint": "提示：在那个地方睡床可不安全。",
        },
        {
            "id": "survival_end_portal",
            "category": "survival",
            "scene": "你准备寻找末地要塞。",
            "stem": "通常用什么来寻找末地要塞方向？",
            "choices": ["末影之眼", "钻石", "罗盘"],
            "correct_index": 0,
            "aliases": ["眼睛", "末影眼"],
            "hint": "提示：把它扔出去会自己飞。",
        },
        {
            "id": "survival_redstone",
            "category": "survival",
            "scene": "你想做一个自动门和机关。",
            "stem": "红石最常用来做什么？",
            "choices": ["电路和机关", "食物", "盔甲"],
            "correct_index": 0,
            "aliases": ["机关", "电路"],
            "hint": "提示：它像 Minecraft 里的电线。",
        },
        {
            "id": "survival_sugar_cane",
            "category": "survival",
            "scene": "你想种点甘蔗做纸。",
            "stem": "甘蔗一般要种在什么旁边？",
            "choices": ["水边", "岩浆边", "树上"],
            "correct_index": 0,
            "aliases": ["河边", "水旁边"],
            "hint": "提示：离开液体它长不好。",
        },
        {
            "id": "survival_cactus_use",
            "category": "survival",
            "scene": "你在沙漠里发现很多仙人掌。",
            "stem": "仙人掌常见的实用用途之一是什么？",
            "choices": ["销毁不要的物品", "做床", "做火把"],
            "correct_index": 0,
            "aliases": ["销毁物品", "垃圾桶"],
            "hint": "提示：掉进去的东西很容易没掉。",
        },
        {
            "id": "survival_ender_chest",
            "category": "survival",
            "scene": "你把重要战利品放进了末影箱。",
            "stem": "末影箱最特别的地方是什么？",
            "choices": ["所有末影箱共享同一格子空间", "容量无限大", "只能装食物"],
            "correct_index": 0,
            "aliases": ["共享空间", "联通箱子"],
            "hint": "提示：别的末影箱也能看到同样的内容。",
        },
        {
            "id": "survival_shulker_box",
            "category": "survival",
            "scene": "你拿到了一个潜影盒，准备装很多物品出门。",
            "stem": "潜影盒最大的特点是什么？",
            "choices": ["打破后里面的东西还能保留", "只能装方块", "会自动整理背包"],
            "correct_index": 0,
            "aliases": ["保留物品", "东西还在里面"],
            "hint": "提示：它很适合搬家和远行。",
        },
        {
            "id": "survival_elytra_source",
            "category": "survival",
            "scene": "你想在天上滑翔飞行。",
            "stem": "鞘翅通常从哪里获得？",
            "choices": ["末地船", "下界要塞", "沙漠神殿"],
            "correct_index": 0,
            "aliases": ["末地的船", "末地飞船"],
            "hint": "提示：它在末地城附近的特殊建筑里。",
        },
        {
            "id": "survival_beacon_base",
            "category": "survival",
            "scene": "你想点亮信标，让它给你加成。",
            "stem": "激活信标时，底座通常要用什么块？",
            "choices": ["铁块、金块、钻石块或绿宝石块", "泥土块", "木板"],
            "correct_index": 0,
            "aliases": ["矿块", "铁块金块这些"],
            "hint": "提示：都是比较高级的矿物方块。",
        },
        {
            "id": "survival_water_bucket",
            "category": "survival",
            "scene": "你从高处往下掉，想保命。",
            "stem": "很多玩家下落保命时爱用什么？",
            "choices": ["水桶", "苹果", "木门"],
            "correct_index": 0,
            "aliases": ["装水的桶", "桶水"],
            "hint": "提示：落地前放出来会变软着陆。",
        },
        {
            "id": "survival_totem",
            "category": "survival",
            "scene": "你准备打一场很危险的战斗。",
            "stem": "不死图腾最厉害的作用是什么？",
            "choices": ["濒死时救你一次", "让你跑更快", "自动修装备"],
            "correct_index": 0,
            "aliases": ["救命一次", "复活一次"],
            "hint": "提示：名字里就有“不死”两个字。",
        },
    ]


class MinecraftQuizGame(BaseGame):
    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self.question_bank = _build_question_bank()
        self._unused_question_ids: List[str] = []

    def get_opening(self) -> str:
        return "太棒了！欢迎来到我的世界大冒险！准备好了吗？第一题来咯！"

    def _pick_question(self) -> Dict:
        if not self._unused_question_ids:
            self._unused_question_ids = [q["id"] for q in self.question_bank]
            self.rng.shuffle(self._unused_question_ids)

        question_id = self._unused_question_ids.pop()
        return next(q for q in self.question_bank if q["id"] == question_id)

    def _build_answer_payload(self, question: Dict, shuffled_indices: List[int]) -> Dict:
        options: Dict[str, str] = {}
        normalized_option_texts: Dict[str, str] = {}
        correct_option = "A"
        for label, choice_index in zip(OPTION_LABELS, shuffled_indices):
            option_text = question["choices"][choice_index]
            options[label] = option_text
            normalized_option_texts[label] = _normalize_text(option_text)
            if choice_index == question["correct_index"]:
                correct_option = label

        correct_text = question["choices"][question["correct_index"]]
        return {
            "question_id": question["id"],
            "category": question["category"],
            "options": options,
            "normalized_option_texts": normalized_option_texts,
            "correct_option": correct_option,
            "correct_text": correct_text,
            "accepted_texts": _expand_accepted_texts(
                correct_text, question.get("aliases", [])
            ),
            "hint": question["hint"],
        }

    def generate_question(
        self,
        round_index: int,
        consecutive_correct: int,
        consecutive_wrong: int,
    ) -> Tuple[str, Dict, int]:
        question = self._pick_question()
        shuffled_indices = [0, 1, 2]
        self.rng.shuffle(shuffled_indices)
        answer = self._build_answer_payload(question, shuffled_indices)

        question_text = (
            f"{question['scene']}\n"
            f"{question['stem']}\n"
            f"A. {answer['options']['A']}\n"
            f"B. {answer['options']['B']}\n"
            f"C. {answer['options']['C']}"
        )
        return question_text, answer, 15

    def normalize_input(self, user_text: str) -> str:
        normalized = _normalize_text(user_text)
        option_label = _normalize_option_alias(normalized)
        if option_label:
            return option_label

        prefixes = ("我选", "答案是", "我觉得是", "应该是", "就是", "选")
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        option_label = _normalize_option_alias(normalized)
        if option_label:
            return option_label
        return normalized

    def check_answer(self, normalized_input: str, answer: Dict) -> bool:
        if not normalized_input:
            return False
        if normalized_input.upper() == answer["correct_option"]:
            return True
        if normalized_input in answer["accepted_texts"]:
            return True
        return normalized_input == answer["normalized_option_texts"][answer["correct_option"]]

    def on_correct(self, consecutive_correct: int, consecutive_wrong: int) -> None:
        return None

    def on_wrong(self, consecutive_correct: int, consecutive_wrong: int) -> None:
        return None

    def get_hint(self, answer: Dict) -> str:
        return answer["hint"]

    def get_wrong_feedback(self, normalized_input: str, answer: Dict) -> str:
        return (
            f"没关系，这题正确答案是{answer['correct_option']}，"
            f"{answer['correct_text']}哦。"
        )

    def format_answer(self, answer: Dict) -> str:
        return f"{answer['correct_option']}，{answer['correct_text']}"


GAME_REGISTRY["minecraft_quiz"] = {
    "class": MinecraftQuizGame,
    "keywords": ["我的世界", "玩我的世界", "minecraft", "mc问答", "mc", "我的世界问答"],
    "name": "Minecraft 趣味问答",
}
