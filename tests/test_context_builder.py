"""受限上下文构造测试。"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from domain.entities import ConversationTopic, MemoryItem, Message
from domain.enums import Role, ScopeLabel, TopicStatus
from services.context_builder import ContextBuilder, _estimate_tokens


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


def test_filters_other_topic_refusal_and_unpaired_messages():
    current_topic = _topic(label="T恤洗护")
    other_topic = uuid4()
    valid_turn = uuid4()
    refusal_turn = uuid4()
    unpaired_turn = uuid4()
    messages = [
        _message(current_topic.id, valid_turn, "human", "纯棉T恤会缩水吗"),
        _message(current_topic.id, valid_turn, "ai", "高温洗涤可能缩水"),
        _message(other_topic, uuid4(), "human", "股票行情"),
        _message(
            current_topic.id,
            refusal_turn,
            "human",
            "无关问题",
            is_refusal=True,
            memory_eligible=False,
            scope_label="OUT",
        ),
        _message(current_topic.id, unpaired_turn, "human", "未完成问题"),
    ]

    context = ContextBuilder(max_tokens=1000).build(
        current_message="那它怎么洗？",
        topic=current_topic,
        recent_messages=messages,
        memories=[],
    )

    assert "股票行情" not in context
    assert "无关问题" not in context
    assert "未完成问题" not in context
    assert "纯棉T恤会缩水吗" in context
    assert "高温洗涤可能缩水" in context


def test_topic_context_rejects_messages_without_topic_id():
    current_topic = _topic(label="T恤洗护")
    turn = uuid4()
    messages = [
        _message(None, turn, "human", "没有主题归属的问题"),
        _message(None, turn, "ai", "不应进入当前主题"),
        _message(current_topic.id, turn, "human", "当前主题问题"),
        _message(current_topic.id, turn, "ai", "当前主题回答"),
    ]

    context = ContextBuilder().build(
        current_message="继续追问",
        topic=current_topic,
        recent_messages=messages,
        memories=[],
    )

    assert "没有主题归属的问题" not in context
    assert "当前主题问题" in context


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

    assert _estimate_tokens(context) <= 220
    assert "CURRENT_USER_MESSAGE:" in context
    assert "USER_PREFERENCES:" in context
    assert "常用尺码 L" in context
    assert "用户参数。" * 20 not in context


def test_expired_memory_is_not_injected():
    topic = _topic(label="T恤推荐")
    memory = _memory(
        memory_key="color",
        content="偏好黑色",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    context = ContextBuilder().build(
        current_message="推荐T恤",
        topic=topic,
        recent_messages=[],
        memories=[memory],
    )
    assert "偏好黑色" not in context
