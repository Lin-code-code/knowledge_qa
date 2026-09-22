"""领域端口定义：应用服务依赖的抽象契约，只使用标准库 `typing.Protocol` 描述，不依赖任何框架。

端口实现方：
- 仓储端口（`ConversationRepositoryPort` / `TopicRepositoryPort` / `MemoryRepositoryPort` / `FileRepositoryPort`）由 `db/` 下的 SQLAlchemy 实现提供；
- AI 能力端口（`ChatAgentPort` / `TopicClassifierPort` / `GuardPort` / `SummaryGeneratorPort` / `MemoryExtractorPort`）由 `agent/` 下的适配器实现；
- 检索端口（`DocumentIndexPort`）由 `rag/` 下的向量库适配器实现。
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.decisions import ChatAnswer, MemoryCandidate, TopicDecision
from domain.entities import Conversation, ConversationTopic, FileSummary, MemoryItem, Message, UploadedFile
from domain.enums import ScopeLabel


class ConversationRepositoryPort(Protocol):
    async def create(self, user_id: str, title: str) -> Conversation: ...
    async def get(self, conversation_id: UUID) -> Conversation | None: ...
    async def list_by_user(self, user_id: str, limit: int = 50, offset: int = 0) -> list[Conversation]: ...
    async def delete(self, conversation_id: UUID) -> bool: ...
    async def get_messages(self, conversation_id: UUID, limit: int = 100) -> list[Message]: ...
    async def get_recent_topic_messages(
        self,
        topic_id: UUID | None,
        *,
        max_turns: int | None = None,
        max_tokens: int | None = None,
    ) -> list[Message]: ...
    async def add_turn(
        self,
        conversation_id: UUID,
        topic_id: UUID | None,
        user_content: str,
        assistant_content: str,
        *,
        intent: str,
        scope_label: ScopeLabel = ScopeLabel.IN,
        is_refusal: bool = False,
        memory_eligible: bool = True,
    ) -> tuple[Message, Message]: ...


class TopicRepositoryPort(Protocol):
    async def get_active(self, conversation_id: UUID) -> ConversationTopic | None: ...
    async def create(
        self,
        conversation_id: UUID,
        topic_label: str = "服装咨询",
        *,
        intent: str | None = None,
        scope_label: ScopeLabel = ScopeLabel.IN,
        confidence: float = 0.0,
    ) -> ConversationTopic: ...
    async def switch(
        self,
        conversation_id: UUID,
        topic_label: str,
        *,
        intent: str | None = None,
        scope_label: ScopeLabel = ScopeLabel.IN,
        confidence: float = 0.0,
    ) -> ConversationTopic: ...
    async def get(self, conversation_id: UUID, topic_id: UUID) -> ConversationTopic | None: ...
    async def list(self, conversation_id: UUID) -> list[ConversationTopic]: ...
    async def archive(self, topic_id: UUID) -> bool: ...
    async def update_metadata(
        self,
        topic_id: UUID,
        *,
        topic_label: str | None = None,
        intent: str | None = None,
        scope_label: ScopeLabel | None = None,
        confidence: float | None = None,
    ) -> None: ...
    async def update_summary(self, topic_id: UUID, summary: str, expected_version: int) -> bool: ...


class MemoryRepositoryPort(Protocol):
    async def list_active(self, user_id: str, limit: int = 12) -> list[MemoryItem]: ...
    async def upsert(
        self,
        *,
        user_id: str,
        memory_type: str,
        memory_key: str,
        content: str,
        source_message_id: int | None,
        confidence: float,
        expires_at: datetime | None = None,
    ) -> MemoryItem: ...
    async def delete_one(self, user_id: str, memory_id: UUID) -> bool: ...
    async def delete_all(self, user_id: str) -> int: ...


class FileRepositoryPort(Protocol):
    async def get_by_md5(self, md5_hex: str) -> UploadedFile | None: ...
    async def save(self, file_id: UUID, filename: str, md5_hex: str, file_size: int) -> UploadedFile: ...
    async def list_all(self) -> list[FileSummary]: ...
    async def delete_by_id(self, file_id: UUID) -> bool: ...
    async def delete_index_records(self, file_id: str) -> int: ...


class ChatAgentPort(Protocol):
    async def execute(self, query: str, context: str, topic_label: str) -> ChatAnswer: ...


class TopicClassifierPort(Protocol):
    def route(
        self,
        message: str,
        *,
        topic: ConversationTopic | None = None,
        recent_messages: list[Message] | None = None,
        memories: list[MemoryItem] | None = None,
    ) -> TopicDecision: ...


class GuardPort(Protocol):
    def check_question_scope(self, query: str) -> bool: ...
    def check(self, query: str, answer: str) -> tuple[bool, str]: ...
    @property
    def refusal_text(self) -> str: ...


class SummaryGeneratorPort(Protocol):
    def summarize(self, topic: ConversationTopic, user_message: str, answer: str) -> str | None: ...


class MemoryExtractorPort(Protocol):
    def extract(self, user_message: str) -> list[MemoryCandidate]: ...


class DocumentIndexPort(Protocol):
    def load_document(self, file_id: str, target_path: str) -> list[str] | None: ...
    def delete_documents(self, ids: list[str]) -> None: ...


class AsyncDocumentReader(Protocol):
    async def read(self, size: int) -> bytes: ...
