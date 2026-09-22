import os

from core.config import rag_conf
from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.embeddings import Embeddings
from langchain.chat_models import BaseChatModel


def get_chat_model(model_name: str = None) -> BaseChatModel:
    return init_chat_model(
        model=model_name or rag_conf["chat_model_name"],
        model_provider="openai",
        base_url=rag_conf["deepseek_base_url"],
        api_key=os.environ.get('DEEPSEEK_API_KEY'),
        max_tokens=512,
        reasoning=None
    )

def get_embed_model() -> Embeddings:
    return init_embeddings(
        model=rag_conf["embedding_model_name"],
        provider="openai",
        base_url=rag_conf["siliconflow_base_url"],
        api_key=os.environ.get('SILICONFLOW_API_KEY'),
        chunk_size=64
    )

def get_reranker():
    from rag.model.reranker import RerankClient
    return RerankClient()

def get_rewrite_model() -> BaseChatModel:
    return init_chat_model(
        model=rag_conf["rewrite_model_name"],
        model_provider="openai",
        base_url=rag_conf["siliconflow_base_url"],
        api_key=os.environ.get('SILICONFLOW_API_KEY')
    )


if __name__ == '__main__':
    # 测试聊天模型
    chat_model = get_chat_model()
    response = chat_model.invoke("你好，你可以做什么？")
    print(response.content)

    # 测试嵌入模型
    embed_model = get_embed_model()
    vec = embed_model.embed_query("今天天气真不错")
    print(len(vec))
    print(vec)

    # 测试改写模型
    rewrite_model = get_rewrite_model()
    res = rewrite_model.invoke("今天太阳真好。帮我扩写一下这句话，使得描述生动形象。")
    print(res.content)