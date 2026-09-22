from datetime import datetime, timezone
from uuid import UUID, uuid4

from db.mappers import to_conversation, to_message, to_topic
from domain.enums import Role, ScopeLabel, TopicStatus


def test_conversation_mapper_preserves_fields():
    now = datetime.now(timezone.utc)
    row_id = uuid4()
    from db.models.conversation import Conversation

    row = Conversation(id=row_id, user_id="u1", title="会话", created_at=now, updated_at=now)
    item = to_conversation(row)
    assert item.id == row_id
    assert item.user_id == "u1"
    assert item.created_at == now


def test_message_and_topic_mappers_convert_enums():
    now = datetime.now(timezone.utc)
    conv_id = uuid4()
    topic_id = uuid4()
    from db.models.conversation import ConversationTopic, Message

    message = Message(
        id=1,
        conversation_id=conv_id,
        topic_id=topic_id,
        turn_id=uuid4(),
        role="human",
        content="怎么洗",
        scope_label="IN",
        is_refusal=False,
        memory_eligible=True,
        created_at=now,
    )
    topic = ConversationTopic(
        id=topic_id,
        conversation_id=conv_id,
        topic_label="T恤洗护",
        summary="",
        last_intent="care",
        scope_label="IN",
        confidence=0.9,
        status="active",
        summary_version=0,
        created_at=now,
        updated_at=now,
    )
    assert to_message(message).role == Role.HUMAN
    assert to_message(message).scope_label == ScopeLabel.IN
    assert to_topic(topic).status == TopicStatus.ACTIVE
