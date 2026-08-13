import contextvars

from agent.retrieval_agent import get_retrieval_agent
from agent.rewrite_agent import get_rewrite_agent
from core.config import rag_conf
from utils.prompt_loader import load_refusal_template

# 请求级 sources 收集器：contextvar 持有可变 list，RagService 是进程级单例，
# 不能用实例属性跨请求共享（并发会互相覆盖）。工具在 run_in_executor 线程内
# mutate 该 list（同一对象），父协程可见。
_sources_ctx: contextvars.ContextVar[list[str]] = contextvars.ContextVar(
    "rag_sources", default=None
)


def start_sources_collection() -> contextvars.Token:
    return _sources_ctx.set([])


def collect_sources() -> list[str]:
    return _sources_ctx.get() or []


class RagService:
    def __init__(self):
        self._refusal_text = load_refusal_template()
        self._rewriter = get_rewrite_agent()
        self._rewrite_enabled = rag_conf.get("query_rewrite_enabled", True)

    def rag_summarize(self, query: str) -> str:
        if self._rewrite_enabled:
            query = self._rewriter.rewrite(query)
        context_docs = get_retrieval_agent().retrieve(query)

        collector = _sources_ctx.get()
        if collector is not None:
            for doc in context_docs:
                source_title = doc.metadata.get('source', '未知来源').split("\\")[-1]
                if source_title not in collector:
                    collector.append(source_title)

        if not context_docs:
            return self._refusal_text

        parts = []
        for i, doc in enumerate(context_docs):
            parts.append(f"[参考资料{i+1}]: {doc.page_content}")
        return "\n".join(parts)

