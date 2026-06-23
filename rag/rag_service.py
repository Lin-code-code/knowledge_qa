import time
from collections import OrderedDict
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from rag.model.factory import get_chat_model
from core.config import rag_conf
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

    def _init_chain(self):
        chain = self.prompt | self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str) -> list[Document]:
        cached = self._cache.get(query)
        if cached is not None:
            return cached
        docs = self.retriever.invoke(query)
        self._cache.set(query, docs)
        return docs

    def get_sources(self) -> list:
        sources = []
        for doc in self._last_docs:
            source_title = doc.metadata.get('source', '未知来源').split("\\")[-1]
            sources.append(source_title)
        return sources

    def rag_summarize(self, query: str) -> str:
        context_docs = self.retriever_docs(query)
        self._last_docs = context_docs

        context = ""
        cnt = 0
        for doc in context_docs:
            cnt += 1
            context += f"[参考资料{cnt}]: {doc.page_content} | 参考源数据：{doc.metadata}\n"

        return self.chain.invoke(
            {
                "input": query,
                "context": context
            }
        )

    if __name__ == '__main__':
        # rag = RagService()
        # print(rag.rag_summarize("扫地机器人是如何实现自主导航的？"))
        pass
