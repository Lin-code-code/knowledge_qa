import json
import re
import asyncio
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from core.config import db_conf
from core.logger import logger
from db.memory_repo import MemoryRepository
from models.conversation import Message
from rag.model.factory import get_rewrite_model
from utils.prompt_loader import load_memory_prompt

_ALLOWED_KEYS = {"size", "color", "material", "wearing_restriction"}
# 每个记忆类别对应的查询触发词；命中当前问题时才注入该类偏好，避免无关偏好污染上下文。
_INTENT_KEYWORDS = {
    "size": ("尺码", "身高", "体重", "穿多大", "什么码", "几码"),
    "color": ("颜色", "色系", "肤色", "深色", "浅色", "黑色", "白色"),
    "material": ("面料", "材质", "纯棉", "棉", "羊毛", "羊绒", "麻", "真丝", "涤纶", "针织"),
    "wearing_restriction": ("过敏", "不能穿", "不穿", "穿不了", "避免", "限制", "怕冷", "怕热"),
}
# 通用选购/搭配意图：命中时四类服装偏好都可以作为参考注入。
_SHOPPING_KEYWORDS = ("推荐", "买", "选购", "挑", "适合", "搭配", "穿搭", "换季", "购物", "下单")
_SHOPPING_INTENTS = {"recommendation", "recommend", "shopping", "purchase", "buy"}


def _content(response) -> str:
    value = getattr(response, "content", response)
    if isinstance(value, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in value)
    return str(value)


class MemoryService:
    def __init__(self, repository: MemoryRepository, model=None):
        self.repository = repository
        self.model = model or get_rewrite_model()
        self.prompt = load_memory_prompt()
        self.threshold = db_conf.get("memory_confidence_threshold", 0.8)

    async def list_for_prompt(self, user_id: str) -> list:
        if not user_id or user_id == "anonymous":
            return []
        return await self.repository.list_active(
            user_id, limit=db_conf.get("memory_max_items", 12)
        )

    def select_for_query(
        self,
        memories: list,
        query: str,
        intent: str | None = None,
    ) -> list:
        """按当前问题/意图筛选相关偏好，只把真正有用的偏好交给 Agent。"""
        if not memories:
            return []
        intent_lower = (intent or "").lower()
        if intent_lower in _SHOPPING_INTENTS:
            return [
                item for item in memories if item.memory_key in _INTENT_KEYWORDS
            ]
        if intent_lower in _INTENT_KEYWORDS:
            return [
                item
                for item in memories
                if item.memory_key == intent_lower
            ]
        text = query or ""
        shopping = any(word in text for word in _SHOPPING_KEYWORDS)
        selected = []
        for item in memories:
            if item.memory_key not in _INTENT_KEYWORDS:
                continue
            if shopping:
                selected.append(item)
            elif any(word in text for word in _INTENT_KEYWORDS[item.memory_key]):
                selected.append(item)
        return selected

    async def extract_and_save(
        self,
        *,
        user_id: str,
        user_message: str,
        source_message: Message | None,
    ) -> None:
        if not user_id or user_id == "anonymous":
            return
        candidates = await asyncio.to_thread(self._extract_with_model, user_message)
        for candidate in candidates:
            if (
                candidate["memory_key"] not in _ALLOWED_KEYS
                or candidate["confidence"] < self.threshold
                or not self._is_explicit(user_message, candidate["memory_key"])
            ):
                continue
            expires_at = None
            if candidate.get("expires_at"):
                try:
                    expires_at = datetime.fromisoformat(candidate["expires_at"])
                except ValueError:
                    expires_at = None
            await self.repository.upsert(
                user_id=user_id,
                memory_type="preference",
                memory_key=candidate["memory_key"],
                content=candidate["content"][:500],
                source_message_id=source_message.id if source_message else None,
                confidence=candidate["confidence"],
                expires_at=expires_at,
            )

    def _extract_with_model(self, user_message: str) -> list[dict]:
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
                    {
                        "memory_key": str(item.get("memory_key", "")),
                        "content": str(item.get("content", "")),
                        "confidence": float(item.get("confidence", 0)),
                        "expires_at": item.get("expires_at"),
                    }
                    for item in data
                    if isinstance(item, dict)
                ]
        except Exception as exc:
            logger.warning("[MemoryService] 长期记忆提取失败: %s", exc)
        return []

    @staticmethod
    def _is_explicit(text: str, key: str) -> bool:
        if key == "size":
            return bool(re.search(r"(我|本人).{0,8}(平时|通常|常用|穿着|穿).{0,8}(XS|XXS|S|M|L|XL|XXL|\d+码)", text, re.I))
        if key == "color":
            return bool(re.search(r"(我|本人).{0,8}(喜欢|偏好|常穿|更喜欢).{0,8}[\u4e00-\u9fff]{1,8}色", text))
        if key == "material":
            return bool(re.search(r"(我|本人).{0,8}(喜欢|偏好|更喜欢).{0,12}(纯棉|棉|羊毛|羊绒|麻|真丝|涤纶|面料|材质)", text))
        return bool(re.search(r"(我|本人).{0,8}(不能|不穿|避免|过敏|限制)", text))
