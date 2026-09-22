from functools import lru_cache

from domain.decisions import ChatAnswer
from rag.rag_service import (
    collect_sources,
    reset_sources_collection,
    reset_topic_context,
    start_sources_collection,
    start_topic_context,
)


@lru_cache(maxsize=1)
def get_chat_agent() -> "ChatAgent":
    return ChatAgent()


class ChatAgent:
    def __init__(self, agent=None):
        from agent.react_agent import ReactAgent

        self.agent = agent or ReactAgent()

    async def execute(self, query: str, context: str, topic_label: str) -> ChatAnswer:
        source_token = start_sources_collection()
        topic_token = start_topic_context(topic_label)
        try:
            answer = await self.agent.aexecute(query, context)
            return ChatAnswer(answer=answer, sources=list(collect_sources()))
        finally:
            reset_sources_collection(source_token)
            reset_topic_context(topic_token)
