import os
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.language_models import BaseChatModel
from utils.config_handler import rag_conf

from langchain_openai.chat_models import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings


def get_chat_model() -> BaseChatModel:
    return ChatTongyi(model=rag_conf["chat_model_name"])


def get_embed_model() -> OllamaEmbeddings:
    return OllamaEmbeddings(model=rag_conf["ol_embedding_model_name"], base_url="http://127.0.0.1:11434")


def get_openai_chat_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=rag_conf["openai_chat_model_name"],
        base_url="https://api.siliconflow.cn/v1",
        api_key=os.environ.get('SILICONFLOW_API_KEY')
    )


def get_openai_embed_model() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        base_url="https://api.siliconflow.cn/v1",
        model=rag_conf["openai_embedding_model_name"],
        api_key=os.environ.get('SILICONFLOW_API_KEY'),
        chunk_size=64
    )

if __name__ == '__main__':
    res = get_openai_embed_model().embed_query("今天天气如何？")
    print(len(res))
    print(res)

    res1 = get_openai_chat_model().stream([{"role": "user", "content": "你是谁？可以做什么？"}])
    for chunk in res1:
        print(chunk.content, end="", flush=True)

