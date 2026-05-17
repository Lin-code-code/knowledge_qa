from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from model.factory import chat_model
from utils.path_tool import get_abs_path
import yaml
import asyncio


_config_path = get_abs_path("config/database.yml")
with open(_config_path, "r", encoding="utf-8") as f:
    db_conf = yaml.load(f, Loader=yaml.FullLoader)

LLM_MAX_CONCURRENCY = db_conf.get("llm_max_concurrency", 50)

_semaphore = asyncio.Semaphore(LLM_MAX_CONCURRENCY)

_vector_store = VectorStoreService()
_retriever = _vector_store.get_retriver()

_system_prompt_template = load_rag_prompts()

_prompt = ChatPromptTemplate.from_messages([
    ("system", _system_prompt_template),
    MessagesPlaceholder("history"),
    ("human", "{input}"),
])

_chain = _prompt | chat_model | StrOutputParser()


def _build_context(query: str) -> str:
    """从向量库检索相关文档，构建 RAG 上下文"""
    docs = _retriever.invoke(query)
    context = ""
    for i, doc in enumerate(docs, 1):
        context += f"[参考资料{i}]: {doc.page_content}\n"
    return context


async def invoke_chain(query: str, history: list) -> str:
    """
    调用 LCEL 问答链，带并发限流。
    将 {context} 作为变量传入 ChatPromptTemplate，
    由模板引擎自动完成 system prompt 中的上下文注入。
    """
    context = _build_context(query)

    async with _semaphore:
        response = await _chain.ainvoke({
            "context": context,
            "history": history,
            "input": query,
        })

    return response


def get_sources(query: str) -> list:
    """获取检索来源列表"""
    docs = _retriever.invoke(query)
    sources = []
    for doc in docs:
        source_title = doc.metadata.get('source', '未知来源')
        sources.append(source_title)
    return sources
