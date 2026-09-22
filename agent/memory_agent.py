import json
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage

from core.logger import logger
from domain.decisions import MemoryCandidate
from rag.model.factory import get_rewrite_model
from utils.prompt_loader import load_memory_prompt


def _content(response) -> str:
    value = getattr(response, "content", response)
    if isinstance(value, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in value)
    return str(value)


@lru_cache(maxsize=1)
def get_memory_extractor() -> "MemoryExtractor":
    return MemoryExtractor()


class MemoryExtractor:
    def __init__(self, model=None):
        self.model = model or get_rewrite_model()
        self.prompt = load_memory_prompt()

    def extract(self, user_message: str) -> list[MemoryCandidate]:
        try:
            response = self.model.invoke(
                [
                    SystemMessage(content=self.prompt),
                    HumanMessage(content=user_message),
                ]
            )
            raw = _content(response)
            start, end = raw.find("["), raw.rfind("]")
            if start >= 0 and end > start:
                data = json.loads(raw[start:end + 1])
                return [
                    MemoryCandidate(
                        memory_key=str(item.get("memory_key", "")),
                        content=str(item.get("content", "")),
                        confidence=float(item.get("confidence", 0)),
                        expires_at=item.get("expires_at"),
                    )
                    for item in data
                    if isinstance(item, dict)
                ]
        except Exception as exc:
            logger.warning("[MemoryExtractor] 长期记忆提取失败: %s", exc)
        return []
