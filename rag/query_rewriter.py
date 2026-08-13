from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from rag.model.factory import get_ollama_llm
from utils.prompt_loader import load_query_rewrite_prompt
from core.logger import logger


class QueryRewriter:
    def __init__(self):
        self.model = get_ollama_llm()
        self.prompt = PromptTemplate.from_template(load_query_rewrite_prompt())
        self.chain = self.prompt | self.model | StrOutputParser()

    def rewrite(self, query: str) -> str:
        if not query or not query.strip():
            return query

        try:
            rewritten = self.chain.invoke({"query": query})
            result = rewritten.strip()
            logger.info(f"[QueryRewriter] 改写: '{query}' → '{result}'")
            return result
        except Exception as e:
            logger.warning(f"[QueryRewriter] 改写失败，使用原 query: {str(e)}")
            return query
