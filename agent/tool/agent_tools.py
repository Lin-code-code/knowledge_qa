from langchain_core.tools import tool
from rag.rag_service import RagService
from datetime import datetime

rag = RagService()

@tool(description="从向量存储中检索参考资料")
def rag_summarize(query: str) -> str:
    return rag.rag_summarize(query)

@tool(description="获取当前时间，以纯字符串的形式返回")
def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")