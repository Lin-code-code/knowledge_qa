import os
from langchain_core.language_models import BaseChatModel
from core.config import rag_conf
from langchain_openai.chat_models import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_ollama import OllamaLLM

def get_chat_model() -> BaseChatModel:
    return ChatOpenAI(
        model=rag_conf["chat_model_name"],
        base_url="https://api.deepseek.com",
        api_key=os.environ.get('DEEPSEEK_API_KEY')
    )

def get_guard_model() -> BaseChatModel:
    return ChatOpenAI(
        model=rag_conf["guard_model_name"],
        base_url="https://api.siliconflow.cn/v1",
        api_key=os.environ.get("SILICONFLOW_API_KEY"),
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

# def get_ollama_llm():
#     return OllamaLLM(
#         model=rag_conf["guard_model_name"],
#         base_url="http://localhost:11434",
#         reasoning=False
#     )

if __name__ == '__main__':
    result = get_chat_model().invoke("你是谁？")
    for r in result.content:
        print(r, end="", flush=True)


