from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()
FIXED_EXIT_RESPONSE = "再见啦"

handle_exit_intent_function_desc = {
    "type": "function",
    "function": {
        "name": "handle_exit_intent",
        "description": "当用户想结束对话或需要退出系统时调用",
        "parameters": {"type": "object", "properties": {}},
    },
}


@register_function(
    "handle_exit_intent", handle_exit_intent_function_desc, ToolType.SYSTEM_CTL
)
def handle_exit_intent(conn: "ConnectionHandler", say_goodbye: str | None = None):
    conn.is_exiting = True
    # 处理退出意图
    try:
        conn.close_after_chat = True
        logger.bind(tag=TAG).info(f"退出意图已处理:{FIXED_EXIT_RESPONSE}")
        return ActionResponse(
            action=Action.RESPONSE,
            result="退出意图已处理",
            response=FIXED_EXIT_RESPONSE,
        )
    except Exception as e:
        logger.bind(tag=TAG).error(f"处理退出意图错误: {e}")
        return ActionResponse(
            action=Action.NONE, result="退出意图处理失败", response=""
        )
