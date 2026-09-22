import json
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage

from core.logger import logger
from domain.decisions import TopicDecision, TopicSegment
from domain.entities import ConversationTopic, MemoryItem, Message
from domain.enums import ScopeLabel, TopicAction
from rag.model.factory import get_rewrite_model
from utils.prompt_loader import load_topic_router_prompt


def _content(response) -> str:
    value = getattr(response, "content", response)
    if isinstance(value, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in value
        )
    return str(value)


@lru_cache(maxsize=1)
def get_topic_router() -> "TopicRouter":
    return TopicRouter()


class TopicRouter:
    def __init__(self, model=None):
        self.model = model or get_rewrite_model()
        self.prompt = load_topic_router_prompt()

    def route(
        self,
        message: str,
        *,
        topic: ConversationTopic | None = None,
        recent_messages: list[Message] | None = None,
        memories: list[MemoryItem] | None = None,
    ) -> TopicDecision:
        recent_messages = recent_messages or []
        memories = memories or []
        prompt = self.prompt.replace(
            "{{CURRENT_TOPIC_SUMMARY}}", (topic.summary if topic else "") or "暂无"
        ).replace(
            "{{CURRENT_TOPIC_LABEL}}", (topic.topic_label if topic else "") or "暂无"
        ).replace("{{RECENT_TURN}}", self._recent_turn(recent_messages)).replace(
            "{{USER_PREFERENCES}}", self._preferences(memories)
        )
        try:
            response = self.model.invoke(
                [SystemMessage(content=prompt), HumanMessage(content=message)]
            )
            decision = self._parse(_content(response))
            if not decision.canonical_query:
                decision.canonical_query = message.strip()
            return decision
        except Exception as exc:
            logger.warning("[TopicRouter] 路由失败，进入受限降级: %s", exc)
            return self._fallback(message, topic)

    @staticmethod
    def _recent_turn(messages: list[Message]) -> str:
        if not messages:
            return "暂无"
        return "\n".join(
            f"{'用户' if item.role == 'human' else '客服'}：{item.content}"
            for item in messages[-2:]
        )

    @staticmethod
    def _preferences(memories: list[MemoryItem]) -> str:
        return "\n".join(f"- {item.memory_key}: {item.content}" for item in memories) or "暂无"

    @staticmethod
    def _parse(raw: str) -> TopicDecision:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("主题路由未返回 JSON")
        obj = json.loads(raw[start:end + 1])
        action_value = str(obj.get("action", "CONTINUE")).upper()
        if action_value in {"OUT", "OUT_SCOPE", "OUT-OF-SCOPE"}:
            action_value = "OUT_OF_SCOPE"
        action = (
            TopicAction(action_value)
            if action_value in {item.value for item in TopicAction}
            else TopicAction.CONTINUE
        )
        scope = ScopeLabel.OUT if str(obj.get("scope", "IN")).upper() == "OUT" else ScopeLabel.IN
        if scope == ScopeLabel.OUT:
            action = TopicAction.OUT_OF_SCOPE
        raw_segments = obj.get("segments", [])
        if not isinstance(raw_segments, list):
            raw_segments = []
        segments = [
            TopicSegment(
                query=str(item.get("query", "") or "").strip(),
                scope=ScopeLabel.OUT
                if str(item.get("scope", "IN")).upper() == "OUT"
                else ScopeLabel.IN,
                intent=str(item.get("intent", "general") or "general"),
            )
            for item in raw_segments
            if isinstance(item, dict)
        ]
        decision = TopicDecision(
            action=action,
            topic_label=str(obj.get("topic_label", "服装咨询") or "服装咨询"),
            intent=str(obj.get("intent", "general") or "general"),
            canonical_query=str(obj.get("canonical_query", "") or ""),
            scope=scope,
            confidence=max(0.0, min(1.0, float(obj.get("confidence", 0.0)))),
            needs_clarification=action == TopicAction.CLARIFY,
            clarification_question=str(obj.get("clarification_question", "") or ""),
            segments=segments,
        )
        return decision

    @staticmethod
    def _fallback(message: str, topic: ConversationTopic | None) -> TopicDecision:
        text = message.strip()
        # 没有可用主题且问题明显依赖指代时澄清，避免猜测旧上下文。
        context_words = ("它", "那个", "这件", "那件", "上面", "多少钱", "怎么洗", "多少码")
        if topic is None and any(word in text for word in context_words):
            return TopicDecision(
                action=TopicAction.CLARIFY,
                canonical_query=text,
                needs_clarification=True,
                clarification_question="请补充您指的是哪件服装或哪个商品？",
            )
        return TopicDecision(
            action=TopicAction.CONTINUE,
            topic_label=topic.topic_label if topic else "服装咨询",
            intent=topic.last_intent if topic and topic.last_intent else "general",
            canonical_query=text,
            scope=ScopeLabel.IN,
            confidence=0.0,
        )
