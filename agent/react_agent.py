from functools import lru_cache
from langchain.agents import create_agent

from agent.tool.agent_tools import get_current_time, rag_summarize
from agent.tool.middleware import monitor_tool, log_before_model
from rag.model.factory import get_chat_model
from utils.prompt_loader import load_system_prompts


@lru_cache(maxsize=1)
def load_system_prompt_cached() -> str:
    return load_system_prompts()


class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=get_chat_model(),
            system_prompt=load_system_prompt_cached(),
            tools=[rag_summarize, get_current_time],
            middleware=[monitor_tool, log_before_model]
        )

    async def aexecute(self, query: str, context: str = "") -> str:
        user_content = context.strip()
        if not user_content:
            user_content = query
        messages = [{"role": "user", "content": user_content}]

        input_dict = {"messages": messages}
        response = await self.agent.ainvoke(input_dict)
        return response["messages"][-1].content
