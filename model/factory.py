from abc import ABC, abstractmethod
from typing import Optional
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi, BaseChatModel
from utils.config_handler import rag_conf

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[OllamaEmbeddings | BaseChatModel]:
        pass

class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[OllamaEmbeddings | BaseChatModel]:
        return ChatTongyi(model=rag_conf["chat_model_name"])

class EmbeddingModelFactory(BaseModelFactory):
    def generator(self) -> Optional[OllamaEmbeddings | BaseChatModel]:
        return OllamaEmbeddings(model=rag_conf["ol_embedding_model_name"])

chat_model = ChatModelFactory().generator()
embed_model = EmbeddingModelFactory().generator()

if __name__ == '__main__':
    res = embed_model.embed_query("What is the capital of France?")
    print(len(res))