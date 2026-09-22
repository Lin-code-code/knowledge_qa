from functools import lru_cache

from langchain.agents import create_agent

from agent.tool.middleware import log_before_model
from core.logger import logger
from rag.model.factory import get_rewrite_model
from utils.prompt_loader import load_query_rewrite_prompt


@lru_cache(maxsize=1)
def get_rewrite_agent() -> "RewriteAgent":
    return RewriteAgent()


class RewriteAgent:
    def __init__(self):
        self.agent = create_agent(
            model=get_rewrite_model(),
            system_prompt=load_query_rewrite_prompt(),
            tools=[],
            middleware=[log_before_model],
        )

    def rewrite(self, query: str, topic_label: str | None = None) -> str:
        if not query or not query.strip():
            return query

        try:
            prompt = query
            if topic_label:
                prompt = f"当前主题：{topic_label}\n当前检索问题：{query}"
            resp = self.agent.invoke({"messages": [{"role": "user", "content": prompt}]})
            result = resp["messages"][-1].content.strip()
            logger.info(f"[RewriteAgent] 改写: '{query}' → '{result}'")
            return result or query
        except Exception as e:
            logger.warning(f"[RewriteAgent] 改写失败，使用原 query: {str(e)}")
            return query
