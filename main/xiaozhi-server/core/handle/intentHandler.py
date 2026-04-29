import json
import uuid
import asyncio
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
from core.utils.dialogue import Message
from core.providers.tts.dto.dto import ContentType
from core.handle.helloHandle import checkWakeupWords
from plugins_func.register import Action, ActionResponse
from core.handle.sendAudioHandle import send_stt_message
from core.handle.reportHandle import enqueue_tool_report
from core.utils.util import remove_punctuation_and_length
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType
from plugins_func.functions.handle_exit_intent import FIXED_EXIT_RESPONSE
from core.handle.game_session import GameState

# 导入 Minecraft 问答题库（自动注册到 GAME_REGISTRY）
import core.handle.minecraft_quiz  # noqa: F401

TAG = __name__


# ====== 模糊接球：关键词意图分类 ======
# V1 版本：用关键词匹配做粗分类，覆盖 80% 儿童场景即可
# 分类：play_game / chat / unclear
# 不确定时给选项引导，不说"我没听懂"

GAME_KEYWORDS = [
    "玩游戏", "游戏", "猜谜", "猜谜语", "谜语",
    "口算", "算数", "算术", "加减法",
    "闯关", "答题", "考考你", "出题",
    "恐龙问答", "动物问答",
    "我的世界", "mc问答", "玩我的世界",
    "玩数学", "玩口算", "算数游戏", "数学游戏",
    "数字炸弹", "猜数字", "数字游戏", "炸弹", "猜数",
]

CHAT_KEYWORDS = [
    "你好", "嗨", "你在干嘛", "你在做什么",
    "讲故事", "讲个故事", "说说",
    "为什么", "怎么回事", "什么是",
    "你喜欢", "你觉得",
]

# 当文本太短或无法匹配时的引导话术
UNCLEAR_RESPONSES = [
    "嗯…你是想玩游戏呢，还是想跟我聊天呀？",
    "我猜你是想找我玩对不对？想玩猜谜语还是口算呀？",
    "你说的话我有点没听清诶，要不要玩个游戏呀？猜谜语还是口算？",
]


def _has_recent_assistant_message(conn: "ConnectionHandler", lookback: int = 3) -> bool:
    """检查最近几轮对话中是否有 assistant 消息（用于判断是否在对话上下文中）"""
    try:
        messages = conn.dialogue.dialogue
        recent = messages[-lookback:] if messages else []
        return any(m.role == "assistant" for m in recent)
    except Exception:
        return False


def classify_fuzzy_intent(text: str) -> str:
    """基于关键词的模糊意图分类
    返回: 'play_game' / 'chat' / 'unclear'
    """
    if not text or len(text.strip()) == 0:
        return "unclear"

    text_lower = text.strip()

    # 优先匹配游戏关键词
    for kw in GAME_KEYWORDS:
        if kw in text_lower:
            return "play_game"

    # 匹配聊天关键词
    for kw in CHAT_KEYWORDS:
        if kw in text_lower:
            return "chat"

    # 文本太短（ASR 可能识别不完整），给选项引导
    if len(text_lower) <= 3:
        return "unclear"

    # 默认走正常聊天
    return "chat"


async def handle_fuzzy_catch(conn: "ConnectionHandler", text: str) -> bool:
    """模糊接球处理：对孩子说不清楚的话给出引导式回复
    返回 True 表示已处理（不继续走后续流程），False 表示未处理
    """
    # 如果已在游戏中，优先路由到游戏状态机
    if hasattr(conn, 'game_session') and conn.game_session and conn.game_session.is_active:
        return False  # 交给 handle_game_input 处理

    intent = classify_fuzzy_intent(text)
    conn.logger.bind(tag=TAG).info(f"模糊接球分类: '{text}' -> {intent}")

    if intent == "play_game":
        # 尝试匹配具体游戏类型并启动
        from core.handle.game_templates import find_game_by_keyword, create_game
        game_type = find_game_by_keyword(text)
        if game_type:
            return await start_game(conn, game_type, text)
        # 没匹配到具体游戏，走正常 chat 让 LLM 引导
        return False

    if intent == "unclear":
        # 如果在对话上下文中（小智刚问了问题），短回复应传给 LLM
        if _has_recent_assistant_message(conn):
            return False
        # 不确定 — 给引导选项，不冷冰冰地说"听不懂"
        response = random.choice(UNCLEAR_RESPONSES)
        conn.sentence_id = str(uuid.uuid4().hex)
        await send_stt_message(conn, text)
        speak_txt(conn, response)
        return True

    # chat 意图 — 正常走后续流程
    return False


async def start_game(conn: "ConnectionHandler", game_type: str, text: str) -> bool:
    """启动一个游戏"""
    from core.handle.game_templates import create_game
    from core.handle.game_session import GameSession
    from core.handle.game_profile import load_game_profile

    game = create_game(game_type)
    if not game:
        return False

    # 4b: 读取游戏画像，恢复难度/出题策略
    profile = load_game_profile(conn, game_type)
    if profile and hasattr(game, 'restore_from_profile'):
        game.restore_from_profile(profile)

    # 初始化 game_session
    if not hasattr(conn, 'game_session') or conn.game_session is None:
        conn.game_session = GameSession()

    opening = conn.game_session.start(game_type, game)
    conn.sentence_id = str(uuid.uuid4().hex)
    await send_stt_message(conn, text)

    # 播放开场白
    speak_txt(conn, opening)

    # 生成第一题
    question = conn.game_session.next_question()
    if question:
        speak_txt(conn, question)

    return True


async def handle_game_input(conn: "ConnectionHandler", text: str) -> bool:
    """处理游戏中的用户输入
    返回 True 表示已处理，False 表示不在游戏中
    """
    if not hasattr(conn, 'game_session') or not conn.game_session or not conn.game_session.is_active:
        return False

    session = conn.game_session

    # 1. 检查退出/中断（handle_interrupt 内部会调用 finish() 清空状态）
    #    所以需要先保存画像，再让 handle_interrupt 处理
    from core.handle.game_session import EXIT_KEYWORDS as _EXIT_KW
    should_save = False
    for kw in _EXIT_KW:
        if kw in text:
            should_save = True
            break

    if should_save:
        _save_game_stats(conn, session)

    handled, response = session.handle_interrupt(text)
    if handled:
        conn.sentence_id = str(uuid.uuid4().hex)
        await send_stt_message(conn, text)
        if response:
            speak_txt(conn, response)
        return True

    # 2. 判断答案
    is_correct, feedback = session.judge_answer(text)
    conn.sentence_id = str(uuid.uuid4().hex)
    await send_stt_message(conn, text)

    # Multi-guess 游戏（数字炸弹）：答错留在当前题目，不走 next_question
    if session.state == GameState.WAITING:
        speak_txt(conn, feedback)
        return True

    # 3. 下一题或结束
    question = session.next_question()
    if question:
        # 合并反馈和下一题成一段话，避免 sentence_id 冲突导致反馈被截断
        combined = f"{feedback} 下一题，{question}"
        speak_txt(conn, combined)
    else:
        # 没有下一题，只说反馈
        speak_txt(conn, feedback)
        # 4a: 先保存画像（finish() 会清空 game_type 和 game）
        _save_game_stats(conn, session)
        conn.sentence_id = str(uuid.uuid4().hex)
        ending = session.finish()
        speak_txt(conn, ending)

    return True


def _save_game_stats(conn: "ConnectionHandler", session):
    """游戏结束后收集统计并写入 game_profile"""
    from core.handle.game_profile import save_game_profile

    if not session.game_type:
        return

    stats = session.get_stats()
    extra = {}

    # 口算：保存当前难度
    if session.game_type == "math" and hasattr(session.game, 'difficulty'):
        extra["difficulty"] = session.game.difficulty
    # 数字炸弹：保存当前范围上限
    if session.game_type == "number_bomb" and hasattr(session.game, '_max_number'):
        extra["difficulty"] = session.game._max_number

    stats.update(extra)
    save_game_profile(conn, session.game_type, stats)


# ====== 原有逻辑 ======


async def handle_user_intent(conn: "ConnectionHandler", text):
    # 预处理输入文本，处理可能的JSON格式
    try:
        if text.strip().startswith("{") and text.strip().endswith("}"):
            parsed_data = json.loads(text)
            if isinstance(parsed_data, dict) and "content" in parsed_data:
                text = parsed_data["content"]  # 提取content用于意图分析
                conn.current_speaker = parsed_data.get("speaker")  # 保留说话人信息
    except (json.JSONDecodeError, TypeError):
        pass

    # 检查是否有明确的退出命令
    _, filtered_text = remove_punctuation_and_length(text)
    if await check_direct_exit(conn, filtered_text):
        return True

    # 明确再见不被打断
    if conn.is_exiting:
        return True

    # 检查是否是唤醒词
    if await checkWakeupWords(conn, filtered_text):
        return True

    # 游戏模式：如果已在游戏中，直接路由到游戏状态机
    if await handle_game_input(conn, text):
        return True

    # 模糊接球：对孩子说不清楚的话给出引导式回复
    if await handle_fuzzy_catch(conn, text):
        return True

    if conn.intent_type == "function_call":
        # 使用支持function calling的聊天方法,不再进行意图分析
        return False
    # 使用LLM进行意图分析
    intent_result = await analyze_intent_with_llm(conn, text)
    if not intent_result:
        return False
    # 会话开始时生成sentence_id
    conn.sentence_id = str(uuid.uuid4().hex)
    # 处理各种意图
    return await process_intent_result(conn, intent_result, text)


async def check_direct_exit(conn: "ConnectionHandler", text):
    """检查是否有明确的退出命令"""
    _, text = remove_punctuation_and_length(text)
    cmd_exit = conn.cmd_exit
    for cmd in cmd_exit:
        if text == cmd:
            conn.logger.bind(tag=TAG).info(f"识别到明确的退出命令: {text}")
            await send_stt_message(conn, text)
            conn.sentence_id = str(uuid.uuid4().hex)
            conn.is_exiting = True
            conn.close_after_chat = True
            speak_txt(conn, FIXED_EXIT_RESPONSE)
            return True
    return False


async def analyze_intent_with_llm(conn: "ConnectionHandler", text):
    """使用LLM分析用户意图"""
    if not hasattr(conn, "intent") or not conn.intent:
        conn.logger.bind(tag=TAG).warning("意图识别服务未初始化")
        return None

    # 对话历史记录
    dialogue = conn.dialogue
    try:
        intent_result = await conn.intent.detect_intent(conn, dialogue.dialogue, text)
        return intent_result
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"意图识别失败: {str(e)}")

    return None


async def process_intent_result(
    conn: "ConnectionHandler", intent_result, original_text
):
    """处理意图识别结果"""
    try:
        # 尝试将结果解析为JSON
        intent_data = json.loads(intent_result)

        # 检查是否有function_call
        if "function_call" in intent_data:
            # 直接从意图识别获取了function_call
            conn.logger.bind(tag=TAG).debug(
                f"检测到function_call格式的意图结果: {intent_data['function_call']['name']}"
            )
            function_name = intent_data["function_call"]["name"]
            if function_name == "continue_chat":
                return False

            if function_name == "result_for_context":
                await send_stt_message(conn, original_text)
                conn.client_abort = False

                def process_context_result():
                    conn.dialogue.put(Message(role="user", content=original_text))

                    from core.utils.current_time import get_current_time_info

                    current_time, today_date, today_weekday, lunar_date = (
                        get_current_time_info()
                    )

                    # 构建带上下文的基础提示
                    context_prompt = f"""当前时间：{current_time}
                                        今天日期：{today_date} ({today_weekday})
                                        今天农历：{lunar_date}

                                        请根据以上信息回答用户的问题：{original_text}"""

                    response = conn.intent.replyResult(context_prompt, original_text)
                    speak_txt(conn, response)

                conn.executor.submit(process_context_result)
                return True

            function_args = {}
            if "arguments" in intent_data["function_call"]:
                function_args = intent_data["function_call"]["arguments"]
                if function_args is None:
                    function_args = {}
            # 确保参数是字符串格式的JSON
            if isinstance(function_args, dict):
                function_args = json.dumps(function_args)

            function_call_data = {
                "name": function_name,
                "id": str(uuid.uuid4().hex),
                "arguments": function_args,
            }

            await send_stt_message(conn, original_text)
            conn.client_abort = False

            # 准备工具调用参数
            tool_input = {}
            if function_args:
                if isinstance(function_args, str):
                    tool_input = json.loads(function_args) if function_args else {}
                elif isinstance(function_args, dict):
                    tool_input = function_args

            # 上报工具调用
            enqueue_tool_report(conn, function_name, tool_input)

            # 使用executor执行函数调用和结果处理
            def process_function_call():
                conn.dialogue.put(Message(role="user", content=original_text))
                
                # 工具调用超时时间
                tool_call_timeout = int(conn.config.get("tool_call_timeout", 30))
                # 使用统一工具处理器处理所有工具调用
                try:
                    result = asyncio.run_coroutine_threadsafe(
                        conn.func_handler.handle_llm_function_call(
                            conn, function_call_data
                        ),
                        conn.loop,
                    ).result(timeout=tool_call_timeout)
                except Exception as e:
                    conn.logger.bind(tag=TAG).error(f"工具调用失败: {e}")
                    result = ActionResponse(
                        action=Action.ERROR, result="工具调用超时，请一会再试下哈", response="工具调用超时，请一会再试下哈"
                    )

                # 上报工具调用结果
                if result:
                    enqueue_tool_report(conn, function_name, tool_input, str(result.result) if result.result else None, report_tool_call=False)

                    if result.action == Action.RESPONSE:  # 直接回复前端
                        text = result.response
                        if text is not None:
                            speak_txt(conn, text)
                    elif result.action == Action.REQLLM:  # 调用函数后再请求llm生成回复
                        text = result.result
                        conn.dialogue.put(Message(role="tool", content=text))
                        llm_result = conn.intent.replyResult(text, original_text)
                        if llm_result is None:
                            llm_result = text
                        speak_txt(conn, llm_result)
                    elif (
                        result.action == Action.NOTFOUND
                        or result.action == Action.ERROR
                    ):
                        text = result.response if result.response else result.result
                        if text is not None:
                            speak_txt(conn, text)
                    elif function_name != "play_music":
                        # For backward compatibility with original code
                        # 获取当前最新的文本索引
                        text = result.response
                        if text is None:
                            text = result.result
                        if text is not None:
                            speak_txt(conn, text)

            # 将函数执行放在线程池中
            conn.executor.submit(process_function_call)
            return True
        return False
    except json.JSONDecodeError as e:
        conn.logger.bind(tag=TAG).error(f"处理意图结果时出错: {e}")
        return False


def speak_txt(conn: "ConnectionHandler", text):
    # 记录文本
    conn.tts_MessageText = text

    conn.tts.tts_text_queue.put(
        TTSMessageDTO(
            sentence_id=conn.sentence_id,
            sentence_type=SentenceType.FIRST,
            content_type=ContentType.ACTION,
        )
    )
    conn.tts.tts_one_sentence(conn, ContentType.TEXT, content_detail=text)
    conn.tts.tts_text_queue.put(
        TTSMessageDTO(
            sentence_id=conn.sentence_id,
            sentence_type=SentenceType.LAST,
            content_type=ContentType.ACTION,
        )
    )
    conn.dialogue.put(Message(role="assistant", content=text))
