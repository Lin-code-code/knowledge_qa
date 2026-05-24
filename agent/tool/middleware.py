from typing import Callable
from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain.agents import AgentState
from langgraph.types import Command
from langgraph.runtime import Runtime
from utils.logger_handler import logger


@wrap_tool_call
def monitor_tool(
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command]
) -> ToolMessage | Command:
    """
    工具执行监控
    :param request: 请求的数据封装
    :param handler: 执行函数本身
    :return:
    """
    logger.info(f"[monitor_tool]执行工具：{request.tool_call["name"]}")
    logger.info(f"[monitor_tool]工具参数：{request.tool_call['args']}")

    try:
        result = handler(request)
        logger.info(f"[monitor_tool]工具{request.tool_call['name']}调用成功")

        # 如果调用了填充报告工具
        if request.tool_call["name"] == "fill_context_for_report":
            request.runtime.context["report"] = True

        return result
    except Exception as e:
        logger.error(f"[monitor_tool]工具{request.tool_call['name']}调用失败")
        raise e

@before_model
def log_before_model(
        state: AgentState,
        runtime: Runtime
):
    """
    在模型执行前输出日志
    :param state: 整个agent智能体中的状态记录
    :param runtime: 记录整个执行过程中的上下文信息
    :return:
    """
    logger.info(f"[log_before_model]即将调用模型，带有{len(state["messages"])}条消息")
    logger.debug(f"[log_before_model]{type(state['messages'][-1]).__name__} | {state['messages'][-1].content}")
    return None
