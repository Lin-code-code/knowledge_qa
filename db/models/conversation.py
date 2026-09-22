from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    BigInteger,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.models.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(String(64), nullable=False, default="anonymous")
    title = Column(String(256), default="新对话")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    topics = relationship("ConversationTopic", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_conversations_user", "user_id", "updated_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("conversation_topics.id", ondelete="SET NULL"), nullable=True)
    turn_id = Column(UUID(as_uuid=True), nullable=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    intent = Column(String(64), nullable=True)
    scope_label = Column(String(16), nullable=True)
    is_refusal = Column(Boolean, nullable=False, server_default=text("false"), default=False)
    memory_eligible = Column(Boolean, nullable=False, server_default=text("true"), default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")
    topic = relationship("ConversationTopic", back_populates="messages")

    __table_args__ = (
        Index("idx_messages_conv_created", "conversation_id", text("created_at DESC")),
        Index("idx_messages_topic_turn_created", "topic_id", "turn_id", text("created_at DESC")),
    )


class ConversationTopic(Base):
    __tablename__ = "conversation_topics"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_label = Column(String(256), nullable=False, default="服装咨询")
    summary = Column(Text, nullable=False, default="")
    last_intent = Column(String(64), nullable=True)
    scope_label = Column(String(16), nullable=False, default="IN")
    confidence = Column(Float, nullable=False, default=0.0)
    status = Column(String(16), nullable=False, default="active")
    summary_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    conversation = relationship("Conversation", back_populates="topics")
    messages = relationship("Message", back_populates="topic")

    __table_args__ = (
        Index("idx_topics_conversation_status", "conversation_id", "status", "updated_at"),
        Index(
            "uq_topics_one_active",
            "conversation_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )
