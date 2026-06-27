import os
from typing import Sequence
import httpx
from core.config import rag_conf
from core.logger import logger


class RerankClient:
    """SiliconFlow /v1/rerank 客户端，复用 SILICONFLOW_API_KEY。"""

    def __init__(
        self,
        model: str = rag_conf["rerank_model_name"],
        base_url: str = "https://api.siliconflow.cn/v1",
        api_key: str | None = None,
        timeout: float = 10.0,
    ):
        self.model = model
        self.url = f"{base_url}/rerank"
        self.api_key = api_key or os.environ.get("SILICONFLOW_API_KEY")
        if not self.api_key:
            raise RuntimeError("SILICONFLOW_API_KEY 未设置，无法初始化 RerankClient")
        self.timeout = timeout

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: int = rag_conf.get("rerank_top_n", 3),
        return_documents: bool = False,
    ) -> list[dict]:
        """
        对候选文档按与 query 的相关性重排序。
        返回 list[dict]，每个元素含 {index, relevance_score, document?}，按分数降序。
        """
        if not documents:
            return []

        payload = {
            "model": self.model,
            "query": query,
            "documents": list(documents),
            "top_n": top_n,
            "return_documents": return_documents,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(self.url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"[RerankClient] rerank 请求失败: {str(e)}")
            return []

        results = data.get("results", [])
        results.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
        return results


if __name__ == "__main__":
    rc = RerankClient()
    docs = ["纯棉T恤容易缩水建议冷水手洗", "股票今天大涨", "牛仔裤机洗会掉色"]
    res = rc.rerank("棉T恤怎么洗", docs, top_n=2)
    print(res)
