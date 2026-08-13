import os
from langchain_core.language_models import BaseChatModel
from core.config import rag_conf
from langchain_openai.chat_models import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_ollama.chat_models import ChatOllama
from langchain_ollama.llms import OllamaLLM, BaseLLM

def get_chat_model() -> BaseChatModel:
    return ChatOpenAI(
        model=rag_conf["chat_model_name"],
        base_url="https://api.deepseek.com",
        api_key=os.environ.get('DEEPSEEK_API_KEY'),
        max_tokens=512,
        reasoning=None
    )

def get_embed_model() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        base_url="https://api.siliconflow.cn/v1",
        model=rag_conf["embedding_model_name"],
        api_key=os.environ.get('SILICONFLOW_API_KEY'),
        chunk_size=64
    )

def get_reranker():
    from rag.model.reranker import RerankClient
    return RerankClient()

def get_ollama_llm() -> BaseLLM:
    return OllamaLLM(
        model="qwen3.5:4b",
        base_url="http://localhost:11434",
        reasoning=False
    )

def get_ollama_chat_model() -> BaseChatModel:
    """本地 Ollama 聊天模型（create_agent 需要 BaseChatModel，不能用 OllamaLLM）。"""
    return ChatOllama(
        model="qwen3.5:4b",
        base_url="http://localhost:11434",
        reasoning=False,
    )

if __name__ == '__main__':
    # result = get_chat_model().invoke("你是谁？")
    # for r in result.content:
    #     print(r, end="", flush=True)
    #
    # res = get_embed_model().embed_query("你好")
    # print("\n", res)

    result = get_ollama_llm().invoke("请帮我改写以下问题，使其更清晰、简洁、易于理解：\n\n我想知道如何使用Python进行数据分析.")
    print(result)