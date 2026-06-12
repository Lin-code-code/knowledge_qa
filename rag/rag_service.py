from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from utils.load_env import env_conf
from model.factory import get_chat_model

class RagService:
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompts()
        self.prompt = PromptTemplate.from_template(self.prompt_text)
        self.model = get_chat_model()
        self.chain = self._init_chain()
        self._retrieval_cache: dict[str, list[Document]] = {}

    def _init_chain(self):
        chain = self.prompt | self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str) -> list[Document]:
        if query not in self._retrieval_cache:
            self._retrieval_cache[query] = self.retriever.invoke(query)
        return self._retrieval_cache[query]

    def get_sources(self, query: str) -> list:
        docs = self.retriever_docs(query)
        sources = []
        for doc in docs:
            source_title = doc.metadata.get('source', '未知来源').split("\\")[-1]  # 获取文件名作为来源标题
            sources.append(source_title)
        return sources

    def rag_summarize(self, query: str) -> str:
        context_docs = self.retriever_docs(query)

        context = ""
        cnt = 0
        for doc in context_docs:
            cnt += 1
            context += f"[参考资料{cnt}]: 参考资料：{doc.page_content} | 参考源数据：{doc.metadata}\n"

        # 这里的占位符是因为prompt中的rag_summarize.txt提示词模板中有input、context占位符
        return self.chain.invoke(
            {
                "input": query,
                "context": context
            }
        )

if __name__ == '__main__':
    # rag = RagService()
    # print(rag.rag_summarize("扫地机器人是如何实现自主导航的？"))

    a = {3: 5}
    print(a.get(3))
