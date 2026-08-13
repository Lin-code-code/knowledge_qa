import contextvars
import time
from collections import OrderedDict
from functools import lru_cache

from langchain.agents import create_agent
from langchain_core.documents import Document
from langchain_core.tools import tool

from agent.tool.middleware import log_before_model
from core.config import rag_conf, pg_conf
from core.logger import logger
from rag.model.factory import get_chat_model, get_reranker
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_retrieval_prompt

# 请求级最终文档收集器：检索 agent 用同步 invoke，工具与 retrieve 同一线程，
# 工具 mutate 同一个 list（contextvar 持有引用），父协程可见。
_retrieved_docs_ctx: contextvars.ContextVar[list[Document]] = contextvars.ContextVar(
    "retrieved_docs", default=None
)


@lru_cache(maxsize=1)
def get_retrieval_agent() -> "RetrievalAgent":
    return RetrievalAgent()


class _TTLCache:
    """带容量上限与过期时间的简易缓存"""

    def __init__(self, maxsize: int = 100, ttl: float = 600.0):
        self._maxsize = maxsize
        self._ttl = ttl
        self._data: OrderedDict[str, tuple[float, list[Document]]] = OrderedDict()

    def get(self, key: str) -> list[Document] | None:
        if key not in self._data:
            return None
        ts, val = self._data[key]
        if time.time() - ts >= self._ttl:
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return val

    def set(self, key: str, value: list[Document]) -> None:
        self._data[key] = (time.time(), value)
        self._data.move_to_end(key)
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)


@tool
def vector_search(query: str) -> str:
    """从向量库召回候选文档（宽松召回 candidate_k 条）。"""
    agent = get_retrieval_agent()
    scored = agent.vector_store.search_with_scores(query, k=pg_conf.get("candidate_k", 10))
    docs = [d for d, _ in scored]
    collector = _retrieved_docs_ctx.get()
    if collector is not None:
        collector.clear()
        collector.extend(docs)
    logger.info(f"[RetrievalAgent] vector_search 召回 {len(docs)} 条")
    return "\n".join(f"[{i}] {d.page_content[:120]}" for i, d in enumerate(docs))


@tool
def rerank(query: str) -> str:
    """对候选文档做 rerank 精排，并按相关性阈值（rerank_score_min）筛选。"""
    agent = get_retrieval_agent()
    candidates = list(_retrieved_docs_ctx.get() or [])
    results = agent.reranker.rerank(
        query,
        [d.page_content for d in candidates],
        top_n=rag_conf.get("rerank_top_n", 3),
    )
    docs = [
        candidates[r["index"]]
        for r in results
        if "index" in r
        and isinstance(r["index"], int)
        and 0 <= r["index"] < len(candidates)
        and r.get("relevance_score", 0.0) >= rag_conf.get("rerank_score_min", 0.05)
    ]
    collector = _retrieved_docs_ctx.get()
    if collector is not None:
        collector.clear()
        collector.extend(docs)
    logger.info(f"[RetrievalAgent] rerank 后保留 {len(docs)} 条")
    return "\n".join(f"[{i}] {d.page_content}" for i, d in enumerate(docs))


class RetrievalAgent:
    """检索 agent：create_agent 封装（DeepSeek），工具为 vector_search + rerank。进程级单例。"""

    def __init__(self):
        self.vector_store = VectorStoreService()
        self.reranker = get_reranker()
        self._cache = _TTLCache(
            maxsize=rag_conf.get("retrieval_cache_maxsize", 100),
            ttl=rag_conf.get("retrieval_cache_ttl", 600.0),
        )
        self.agent = create_agent(
            model=get_chat_model(),
            system_prompt=load_retrieval_prompt(),
            tools=[vector_search, rerank],
            middleware=[log_before_model]
        )

    def retrieve(self, query: str) -> list[Document]:
        """按 query 检索并返回最终文档列表。LLM 只驱动工具调用，文档经 contextvar 回传。"""
        cached = self._cache.get(query)
        if cached is not None:
            return cached

        token = _retrieved_docs_ctx.set([])
        try:
            try:
                self.agent.invoke({"messages": [{"role": "user", "content": query}]})
                docs = list(_retrieved_docs_ctx.get() or [])
                if not docs:
                    logger.warning("[RetrievalAgent] agent 未产出文档，退化为向量检索 top_n")
                    docs = [d for d, _ in self.vector_store.search_with_scores(
                        query, k=rag_conf.get("rerank_top_n", 3)
                    )]
            except Exception as e:
                logger.error(f"[RetrievalAgent] agent 调用失败，退化为向量检索 top_n: {str(e)}")
                docs = [d for d, _ in self.vector_store.search_with_scores(
                    query, k=rag_conf.get("rerank_top_n", 3)
                )]
        finally:
            _retrieved_docs_ctx.reset(token)

        self._cache.set(query, docs)
        return docs
