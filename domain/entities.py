from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.enums import Role, ScopeLabel, TopicStatus


@dataclass(slots=True)
class Conversation:
    id: UUID
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Message:
    conversation_id: UUID
    role: Role
    content: str
    id: int | None = None
    topic_id: UUID | None = None
    turn_id: UUID | None = None
    intent: str | None = None
    scope_label: ScopeLabel | None = None
    is_refusal: bool = False
    memory_eligible: bool = True
    created_at: datetime | None = None


@dataclass(slots=True)
class ConversationTopic:
    id: UUID
    conversation_id: UUID
    topic_label: str
    summary: str
    last_intent: str | None
    scope_label: ScopeLabel
    confidence: float
    status: TopicStatus
    summary_version: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class MemoryItem:
    id: UUID
    user_id: str
    memory_type: str
    memory_key: str
    content: str
    source_message_id: int | None
    confidence: float
    expires_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class UploadedFile:
    id: UUID
    filename: str
    md5_hex: str
    size: int
    uploaded_at: datetime


@dataclass(slots=True)
class FileSummary:
    id: UUID
    filename: str
    size: int
    chunks: int
