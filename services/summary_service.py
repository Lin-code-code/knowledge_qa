import json
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from core.logger import logger
from models.conversation import ConversationTopic
from rag.model.factory import get_rewrite_model
from utils.prompt_loader import load_summary_prompt


def _content(response) -> str:
    value = getattr(response, "content", response)
    if isinstance(value, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in value)
    return str(value)


@lru_cache(maxsize=1)
def get_summary_service() -> "SummaryService":
    return SummaryService()


class SummaryService:
    def __init__(self, model=None):
        self.model = model or get_rewrite_model()
        self.prompt = load_summary_prompt()

    def summarize(
        self,
        topic: ConversationTopic,
        user_message: str,
        answer: str,
    ) -> str | None:
        prompt = self.prompt.replace("{{TOPIC_LABEL}}", topic.topic_label).replace(
            "{{OLD_SUMMARY}}", topic.summary or "暂无"
        )
        try:
            response = self.model.invoke(
                [
                    SystemMessage(content=prompt),
                    HumanMessage(content=f"用户：{user_message}\n客服：{answer}"),
                ]
            )
            raw = _content(response).strip()
            start, end = raw.find("{"), raw.rfind("}")
            if start >= 0 and end > start:
                raw = str(json.loads(raw[start:end + 1]).get("summary", "")).strip()
            raw = raw.strip("` \n")
            return raw[:4000] or None
        except Exception as exc:
            logger.warning("[SummaryService] 摘要更新失败，保留旧摘要: %s", exc)
            return None
