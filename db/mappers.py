from domain.entities import Conversation, ConversationTopic, FileSummary, MemoryItem, Message, UploadedFile
from domain.enums import Role, ScopeLabel, TopicStatus
from db.models.conversation import Conversation as ConversationModel
from db.models.conversation import ConversationTopic as TopicModel
from db.models.conversation import Message as MessageModel
from db.models.memory_item import MemoryItem as MemoryModel
from db.models.uploaded_file import UploadedFile as FileModel


def to_scope_label(value: str | None) -> ScopeLabel | None:
    if value is None:
        return None
    return ScopeLabel.OUT if value == "OUT" else ScopeLabel.IN


def to_conversation(row: ConversationModel) -> Conversation:
    return Conversation(row.id, row.user_id, row.title, row.created_at, row.updated_at)


def to_message(row: MessageModel) -> Message:
    return Message(
        id=row.id,
        conversation_id=row.conversation_id,
        topic_id=row.topic_id,
        turn_id=row.turn_id,
        role=Role(row.role),
        content=row.content,
        intent=row.intent,
        scope_label=to_scope_label(row.scope_label),
        is_refusal=row.is_refusal,
        memory_eligible=row.memory_eligible,
        created_at=row.created_at,
    )


def to_topic(row: TopicModel) -> ConversationTopic:
    return ConversationTopic(
        id=row.id,
        conversation_id=row.conversation_id,
        topic_label=row.topic_label,
        summary=row.summary or "",
        last_intent=row.last_intent,
        scope_label=ScopeLabel(row.scope_label),
        confidence=row.confidence,
        status=TopicStatus(row.status),
        summary_version=row.summary_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def to_memory_item(row: MemoryModel) -> MemoryItem:
    return MemoryItem(
        id=row.id,
        user_id=row.user_id,
        memory_type=row.memory_type,
        memory_key=row.memory_key,
        content=row.content,
        source_message_id=row.source_message_id,
        confidence=row.confidence,
        expires_at=row.expires_at,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def to_uploaded_file(row: FileModel) -> UploadedFile:
    return UploadedFile(row.id, row.filename, row.md5_hex, row.size, row.uploaded_at)


def to_file_summary(row) -> FileSummary:
    data = row._mapping if hasattr(row, "_mapping") else row
    return FileSummary(data["id"], data["filename"], data["size"], data["chunks"])