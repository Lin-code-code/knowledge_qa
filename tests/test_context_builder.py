"""受限上下文构造测试。"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.tokens import estimate_tokens
from domain.entities import ConversationTopic, MemoryItem, Message
from domain.enums import Role, ScopeLabel, TopicStatus
from services.context_builder import ContextBuilder


def _topic(label="T恤洗护", summary=""):
    now = datetime.now(timezone.utc)
    return ConversationTopic(
        id=uuid4(),
        conversation_id=uuid4(),
        topic_label=label,
        summary=summary,
        last_intent=None,
        scope_label=ScopeLabel.IN,
        confidence=0.0,
        status=TopicStatus.ACTIVE,
        summary_version=0,
        created_at=now,
        updated_at=now,
    )


def _memory(**kwargs):
    now = datetime.now(timezone.utc)
    data = {
        "id": uuid4(),
        "user_id": "u1",
        "memory_type": "preference",
        "memory_key": "size",
        "content": "",
        "source_message_id": None,
        "confidence": 0.95,
        "expires_at": None,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    data.update(kwargs)
    return MemoryItem(**data)


def _message(topic_id, turn_id, role, content, **kwargs):
    if kwargs.get("scope_label") is not None:
        kwargs["scope_label"] = ScopeLabel(kwargs["scope_label"])
    return Message(
        conversation_id=uuid4(),
        topic_id=topic_id,
        turn_id=turn_id,
        role=Role(role),
        content=content,
        created_at=datetime.now(timezone.utc),
        **kwargs,
    )


def test_trim_keeps_budget_and_confirmed_preferences():
    topic = _topic(label="T恤推荐", summary="已确认的主题摘要。" * 300)
    turn = uuid4()
    messages = [
        _message(topic.id, turn, "human", "用户参数。" * 120),
        _message(topic.id, turn, "ai", "建议内容。" * 120),
    ]
    memory = _memory(
        memory_key="size",
        content="常用尺码 L",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )

    context = ContextBuilder(max_tokens=220).build(
        current_message="推荐一件黑色T恤",
        topic=topic,
        recent_messages=messages,
        memories=[memory],
    )

    assert estimate_tokens(context) <= 220
    assert "CURRENT_USER_MESSAGE:" in context
    assert "USER_PREFERENCES:" in context
    assert "常用尺码 L" in context
    assert "用户参数。" * 20 not in context
