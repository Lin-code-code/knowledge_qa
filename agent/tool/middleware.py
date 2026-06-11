from typing import Callable, Awaitable
from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain.agents import AgentState
from langgraph.types import Command
from langgraph.runtime import Runtime
from utils.logger_handler import logger


@wrap_tool_call
async def monitor_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command] | ToolMessage | Command],
) -> ToolMessage | Command:
    """
    工具执行监控
    """
    tool_name = request.tool_call["name"]
    tool_args = request.tool_call["args"]

    logger.info(f"[monitor_tool]执行工具：{tool_name}")
    logger.info(f"[monitor_tool]工具参数：{tool_args}")

    try:
        result = handler(request)
        if hasattr(result, "__await__"):
            result = await result

        logger.info(f"[monitor_tool]工具{tool_name}调用成功")

        if tool_name == "fill_context_for_report":
            request.runtime.context["report"] = True

        return result
    except Exception as e:
        logger.error(f"[monitor_tool]工具{tool_name}调用失败")
        raise e


@before_model
def log_before_model(
    state: AgentState,
    runtime: Runtime
):
    """
    在模型执行前输出日志
    """
    logger.info(f"[log_before_model]即将调用模型，带有{len(state['messages'])}条消息")
    logger.debug(f"[log_before_model]{type(state['messages'][-1]).__name__} | {state['messages'][-1].content}")
    return None
