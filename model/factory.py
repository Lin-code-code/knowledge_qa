from abc import ABC, abstractmethod
from typing import Optional
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi, BaseChatModel
from utils.config_handler import rag_conf

from langchain_openai.chat_models import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
import os


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[OllamaEmbeddings | BaseChatModel]:
        pass

class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[OllamaEmbeddings | BaseChatModel]:
        return ChatTongyi(model=rag_conf["chat_model_name"])

class EmbeddingModelFactory(BaseModelFactory):
    def generator(self) -> Optional[OllamaEmbeddings | BaseChatModel]:
        return OllamaEmbeddings(model=rag_conf["ol_embedding_model_name"], base_url="http://127.0.0.1:11434")

class ChatModelFactoryOpenAI(BaseModelFactory):
    def generator(self) -> Optional[OllamaEmbeddings | BaseChatModel | ChatOpenAI]:
        return ChatOpenAI(
            model=rag_conf["openai_chat_model_name"],
            base_url="https://api.siliconflow.cn/v1",
            api_key=os.environ.get('SILICONFLOW_API_KEY')
        )

class EmbeddingModelFactoryOpenAI(BaseModelFactory):
    def generator(self) -> Optional[OllamaEmbeddings | BaseChatModel | OpenAIEmbeddings]:
        return OpenAIEmbeddings(
            base_url="https://api.siliconflow.cn/v1",
            model=rag_conf["openai_embedding_model_name"],
            api_key=os.environ.get('SILICONFLOW_API_KEY'),
            chunk_size=64
        )


chat_model = ChatModelFactory().generator()
embed_model = EmbeddingModelFactory().generator()

openai_chat_model = ChatModelFactoryOpenAI().generator()
openai_embed_model = EmbeddingModelFactoryOpenAI().generator()

if __name__ == '__main__':
    # res = embed_model.embed_query("What is the capital of France?")
    # print(len(res))

    res = openai_embed_model.embed_query("今天天气如何？")
    print(len(res))
    print(res)

    res1 = openai_chat_model.stream([{"role": "user", "content": "你是谁？可以做什么？"}])
    for chunk in res1:
        print(chunk.content, end="", flush=True)

