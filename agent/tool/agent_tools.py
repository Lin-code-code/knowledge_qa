from functools import lru_cache
from langchain_core.tools import tool
from datetime import datetime


@lru_cache(maxsize=1)
def get_rag_service():
    from rag.rag_service import RagService
    return RagService()


@tool(description="从向量存储中检索参考资料")
def rag_summarize(query: str) -> str:
    return get_rag_service().rag_summarize(query)

@tool(description="获取当前时间，以纯字符串的形式返回")
def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")