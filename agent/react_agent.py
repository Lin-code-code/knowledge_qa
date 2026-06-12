from functools import lru_cache
from langchain.agents import create_agent

from agent.tool.agent_tools import get_current_time, rag_summarize
from agent.tool.middleware import monitor_tool, log_before_model
from model.factory import get_chat_model
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

    def execute_stream(self, query: str):
        input_dict = {
            "messages": [
                {"role": "user", "content": query}
            ]
        }

        for chunk in self.agent.stream(input_dict, stream_mode="values", context={"report": False}):
            latest_message = chunk["messages"][-1]
            if latest_message.content:
                yield latest_message.content.strip() + "\n"

    async def aexecute(self, query: str, history: list) -> str:
        messages = list(history)
        messages.append({"role": "user", "content": query})
        
        input_dict = {"messages": messages}
        response = await self.agent.ainvoke(input_dict, context={"report": False})
        return response["messages"][-1].content


if __name__ == '__main__':
    agent = ReactAgent()
    for chunk in agent.execute_stream("现在几点了？"):
        print(chunk, end="", flush=True)