import time
from collections import OrderedDict
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts, load_refusal_template
from rag.model.factory import get_chat_model, get_reranker
from rag.query_rewriter import QueryRewriter
from core.config import rag_conf, pg_conf
from core.logger import logger


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


class RagService:
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompts()
        self.prompt = PromptTemplate.from_template(self.prompt_text)
        self.model = get_chat_model()
        self.chain = self._init_chain()
        self._cache = _TTLCache(
            maxsize=rag_conf.get("retrieval_cache_maxsize", 100),
            ttl=rag_conf.get("retrieval_cache_ttl", 600.0),
        )
        self._last_docs: list[Document] = []
        self._reranker = get_reranker()
        self._refusal_text = load_refusal_template()
        self._rewriter = QueryRewriter()
        self._rewrite_enabled = rag_conf.get("query_rewrite_enabled", True)

    def _init_chain(self):
        chain = self.prompt | self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str) -> list[Document]:
        """
        L1 检索：向量检索宽松召回 → Rerank 精排 → rerank score 阈值过滤 → 取 top_n。
        不在 rerank 前做向量距离过滤（向量相似度对语义匹配不准，会误删相关文档）。
        """
        cached = self._cache.get(query)
        if cached is not None:
            return cached

        candidate_k = pg_conf.get("candidate_k", 10)
        top_n = rag_conf.get("rerank_top_n", pg_conf.get("k", 3))
        rerank_score_min = rag_conf.get("rerank_score_min", 0.3)

        scored = self.vector_store.search_with_scores(query, k=candidate_k)
        candidates = [doc for doc, _ in scored]
        if not candidates:
            self._cache.set(query, [])
            return []

        try:
            rerank_results = self._reranker.rerank(
                query=query,
                documents=[doc.page_content for doc in candidates],
                top_n=top_n,
            )
        except Exception as e:
            logger.error(f"[RagService] rerank 失败，退化为向量检索结果: {str(e)}")
            docs = candidates[:top_n]
            self._cache.set(query, docs)
            return docs

        if not rerank_results:
            docs = candidates[:top_n]
            self._cache.set(query, docs)
            return docs

        docs = [
            candidates[r["index"]]
            for r in rerank_results
            if "index" in r and r.get("relevance_score", 0.0) >= rerank_score_min
        ]
        self._cache.set(query, docs)
        return docs

    def get_sources(self) -> list:
        sources = []
        for doc in self._last_docs:
            source_title = doc.metadata.get('source', '未知来源').split("\\")[-1]
            sources.append(source_title)
        return sources

    def rag_summarize(self, query: str) -> str:
        if self._rewrite_enabled:
            query = self._rewriter.rewrite(query)
        context_docs = self.retriever_docs(query)
        self._last_docs = context_docs

        if not context_docs:
            return self._refusal_text

        parts = []
        for i, doc in enumerate(context_docs):
            parts.append(f"[参考资料{i+1}]: {doc.page_content}")
        return "\n".join(parts)

