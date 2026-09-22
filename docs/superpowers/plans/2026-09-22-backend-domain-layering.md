# Backend Domain Layering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有 HTTP、数据库和配置契约的前提下，把后端迁移为 `api -> services -> domain`，并让 `db` 与 `rag/agent` 实现领域端口。

**Architecture:** `domain` 只保存标准库实体、枚举、错误、决策对象和 Protocol；`services` 只依赖这些端口；`db/repositories` 实现持久化端口；`agent/rag` 实现 AI/RAG 端口；`api/dependencies.py` 是唯一组合根。请求级事务继续由 `db/session.py:get_db()` 统一提交或回滚，Repository 不调用 `commit()`。

**Tech Stack:** Python 3.13、FastAPI、SQLAlchemy 2 async、Pydantic、LangChain、PGVector、pytest、uv。

**Spec:** `docs/superpowers/specs/2026-09-22-backend-domain-layering-design.md`

## Global Constraints

- Python 版本必须保持 `>=3.13`，依赖管理必须使用 `uv`。
- 不新增运行时依赖。
- 不修改 `/api/*` 请求字段、响应字段、状态码和现有中文错误文案。
- 不修改数据库表名、列名、迁移脚本语义、`.env` 键或 YAML 配置键。
- `domain` 禁止导入 FastAPI、SQLAlchemy、LangChain、`db`、`services`、`api`、`agent`、`rag`。
- `services` 禁止导入 FastAPI、SQLAlchemy、`db`、`api`、`agent`、`rag`。
- `db` 禁止导入 `services`、`api`、`agent`、`rag`。
- Repository 禁止调用 `session.commit()`；只允许 `flush()`、`refresh()`、`execute()` 和 ORM 对象操作。
- 代码注释使用中文。
- 所有测试命令使用仓库缓存目录：`uv run --cache-dir .uv-cache pytest tests -q`。
- 每个任务结束必须运行该任务测试并提交 Git。
- 每个大阶段结束后同步检查 README；最终必须更新 README、AGENTS.md、changelog.md。

## File Map

- `domain/entities.py`：领域实体和文件读模型。
- `domain/enums.py`：Role、ScopeLabel、TopicAction、TopicStatus。
- `domain/decisions.py`：TopicDecision、TopicSegment、ChatAnswer、MemoryCandidate。
- `domain/errors.py`：领域异常。
- `domain/ports.py`：Repository 与 AI/RAG Protocol。
- `db/mappers.py`：ORM 与领域实体双向转换。
- `db/models/`：SQLAlchemy ORM，不包含业务编排。
- `db/repositories/`：四个 SQLAlchemy Repository 实现。
- `agent/topic_router.py`、`agent/summary_agent.py`、`agent/guard_agent.py`、`agent/memory_agent.py`、`agent/chat_agent.py`：现有 AI 能力适配器。
- `services/conversation_service.py`、`services/topic_service.py`、`services/memory_service.py`、`services/document_service.py`：应用用例。
- `services/chat_service.py`：主问答编排。
- `services/context_builder.py`：纯上下文构造器。
- `api/dependencies.py`：唯一组合根。
- `api/chat.py`、`api/documents.py`：仅 HTTP 路由。

---

### Task 1: 领域实体、枚举、错误和决策对象

**Files:**
- Create: `domain/__init__.py`
- Create: `domain/enums.py`
- Create: `domain/entities.py`
- Create: `domain/errors.py`
- Create: `domain/decisions.py`
- Test: `tests/test_domain_layer.py`

**Interfaces:**
- Consumes: 无。
- Produces: `Role`、`ScopeLabel`、`TopicAction`、`TopicStatus`；`Conversation`、`Message`、`ConversationTopic`、`MemoryItem`、`UploadedFile`、`FileSummary`；`TopicDecision`、`TopicSegment`、`ChatAnswer`、`MemoryCandidate`；`ConversationNotFoundError`、`TopicNotFoundError`、`MemoryNotFoundError`、`DocumentNotFoundError`、`DuplicateDocumentError`、`EmptyDocumentError`、`UnsupportedDocumentTypeError`、`DocumentIndexError`。

- [ ] **Step 1: 写领域层失败测试**

```python
# tests/test_domain_layer.py
import ast
from pathlib import Path

from domain.decisions import TopicDecision
from domain.entities import ConversationTopic, FileSummary
from domain.enums import Role, ScopeLabel, TopicAction


def test_domain_layer_imports_stdlib_only():
    forbidden = {"fastapi", "sqlalchemy", "langchain", "db", "services", "api", "agent", "rag"}
    root = Path(__file__).resolve().parents[1] / "domain"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        assert not (imports & forbidden), f"{path.name} 包含禁止依赖: {imports & forbidden}"


def test_domain_enums_and_defaults_are_stable():
    assert Role.HUMAN == "human"
    assert ScopeLabel.OUT == "OUT"
    assert TopicAction.OUT_OF_SCOPE == "OUT_OF_SCOPE"
    decision = TopicDecision(canonical_query="T恤怎么洗")
    assert decision.action == TopicAction.CONTINUE
    assert decision.scope == ScopeLabel.IN
    assert decision.segments == []


def test_file_summary_is_a_slots_dataclass():
    item = FileSummary(id="f-1", filename="a.txt", size=1, chunks=2)
    assert item.filename == "a.txt"
    assert not hasattr(item, "__dict__")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --cache-dir .uv-cache pytest tests/test_domain_layer.py -q`

Expected: FAIL，报 `ModuleNotFoundError: No module named 'domain'`。

- [ ] **Step 3: 实现领域基础文件**

```python
# domain/enums.py
from enum import Enum


class Role(str, Enum):
    HUMAN = "human"
    AI = "ai"
    SYSTEM = "system"


class ScopeLabel(str, Enum):
    IN = "IN"
    OUT = "OUT"


class TopicAction(str, Enum):
    CONTINUE = "CONTINUE"
    NEW_TOPIC = "NEW_TOPIC"
    MIXED = "MIXED"
    CLARIFY = "CLARIFY"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class TopicStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
```

```python
# domain/entities.py
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
```

```python
# domain/decisions.py
from dataclasses import dataclass, field

from domain.enums import ScopeLabel, TopicAction, TopicStatus


@dataclass(slots=True)
class TopicSegment:
    query: str = ""
    scope: ScopeLabel = ScopeLabel.IN
    intent: str = "general"


@dataclass(slots=True)
class TopicDecision:
    action: TopicAction = TopicAction.CONTINUE
    topic_label: str = "服装咨询"
    intent: str = "general"
    canonical_query: str = ""
    scope: ScopeLabel = ScopeLabel.IN
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_question: str = ""
    segments: list[TopicSegment] = field(default_factory=list)


@dataclass(slots=True)
class ChatAnswer:
    answer: str
    sources: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MemoryCandidate:
    memory_key: str
    content: str
    confidence: float
    expires_at: str | None = None
```

```python
# domain/errors.py
class ConversationNotFoundError(LookupError):
    pass


class TopicNotFoundError(LookupError):
    pass


class MemoryNotFoundError(LookupError):
    pass


class DocumentNotFoundError(LookupError):
    pass


class DuplicateDocumentError(ValueError):
    pass


class EmptyDocumentError(ValueError):
    pass


class UnsupportedDocumentTypeError(ValueError):
    pass


class DocumentIndexError(RuntimeError):
    pass
```

```python
# domain/__init__.py
from domain.entities import Conversation, ConversationTopic, FileSummary, MemoryItem, Message, UploadedFile
from domain.enums import Role, ScopeLabel, TopicAction, TopicStatus

__all__ = [
    "Conversation",
    "ConversationTopic",
    "FileSummary",
    "MemoryItem",
    "Message",
    "UploadedFile",
    "Role",
    "ScopeLabel",
    "TopicAction",
    "TopicStatus",
]
```

- [ ] **Step 4: 运行领域层测试**

Run: `uv run --cache-dir .uv-cache pytest tests/test_domain_layer.py -q`

Expected: `3 passed`。

- [ ] **Step 5: 提交**

```bash
git add domain tests/test_domain_layer.py
git commit -m "refactor(domain): 建立纯领域实体与决策对象"
```

### Task 2: 领域端口与应用契约

**Files:**
- Create: `domain/ports.py`
- Test: `tests/test_domain_ports.py`

**Interfaces:**
- Consumes: Task 1 的实体、枚举、决策和错误。
- Produces: `ConversationRepositoryPort`、`TopicRepositoryPort`、`MemoryRepositoryPort`、`FileRepositoryPort`、`ChatAgentPort`、`TopicClassifierPort`、`GuardPort`、`SummaryGeneratorPort`、`MemoryExtractorPort`、`DocumentIndexPort`、`AsyncDocumentReader`。

- [ ] **Step 1: 写端口契约失败测试**

```python
# tests/test_domain_ports.py
import inspect

from domain.ports import ChatAgentPort, ConversationRepositoryPort


def test_chat_agent_port_exposes_execute_with_topic_label():
    signature = inspect.signature(ChatAgentPort.execute)
    assert list(signature.parameters) == ["self", "query", "context", "topic_label"]


def test_conversation_port_keeps_turn_signature():
    signature = inspect.signature(ConversationRepositoryPort.add_turn)
    assert "user_content" in signature.parameters
    assert "assistant_content" in signature.parameters
    assert "memory_eligible" in signature.parameters
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --cache-dir .uv-cache pytest tests/test_domain_ports.py -q`

Expected: FAIL，报 `ModuleNotFoundError: No module named 'domain.ports'`。

- [ ] **Step 3: 实现端口**

```python
# domain/ports.py
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
```

- [ ] **Step 4: 运行端口测试和领域测试**

Run: `uv run --cache-dir .uv-cache pytest tests/test_domain_layer.py tests/test_domain_ports.py -q`

Expected: `5 passed`。

- [ ] **Step 5: 提交**

```bash
git add domain/ports.py tests/test_domain_ports.py
git commit -m "refactor(domain): 定义仓储与AI能力端口"
```

### Task 3: 迁移 SQLAlchemy ORM 并增加 Mapper

**Files:**
- Move: `models/` -> `db/models/`
- Modify: `db/models/__init__.py`
- Modify: `db/models/conversation.py`
- Modify: `db/models/memory_item.py`
- Modify: `db/models/uploaded_file.py`
- Create: `db/mappers.py`
- Create: temporary compatibility package: `models/__init__.py`, `models/base.py`, `models/conversation.py`, `models/memory_item.py`, `models/uploaded_file.py`
- Test: `tests/test_mappers.py`

**Interfaces:**
- Consumes: Task 1 的领域实体。
- Produces: `to_conversation`、`to_message`、`to_topic`、`to_memory_item`、`to_uploaded_file`、`to_file_summary`、`to_scope_label`。

- [ ] **Step 1: 写 Mapper 失败测试**

```python
# tests/test_mappers.py
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --cache-dir .uv-cache pytest tests/test_mappers.py -q`

Expected: FAIL，报 `ModuleNotFoundError: No module named 'db.mappers'`。

- [ ] **Step 3: 迁移 ORM 并保留临时转发**

```powershell
git mv models db/models
```

将 `db/models/conversation.py`、`memory_item.py`、`uploaded_file.py` 中的 `from models.base import Base` 改为 `from db.models.base import Base`。`db/models/__init__.py` 导出：

```python
from db.models.base import Base
from db.models.conversation import Conversation, ConversationTopic, Message
from db.models.memory_item import MemoryItem
from db.models.uploaded_file import UploadedFile

__all__ = ["Base", "Conversation", "ConversationTopic", "Message", "MemoryItem", "UploadedFile"]
```

重建临时兼容包：

```python
# models/__init__.py
from db.models import Base, Conversation, ConversationTopic, MemoryItem, Message, UploadedFile

__all__ = ["Base", "Conversation", "ConversationTopic", "MemoryItem", "Message", "UploadedFile"]
```

```python
# models/base.py
from db.models.base import Base

__all__ = ["Base"]
```

```python
# models/conversation.py
from db.models.conversation import Conversation, ConversationTopic, Message

__all__ = ["Conversation", "ConversationTopic", "Message"]
```

```python
# models/memory_item.py
from db.models.memory_item import MemoryItem

__all__ = ["MemoryItem"]
```

```python
# models/uploaded_file.py
from db.models.uploaded_file import UploadedFile

__all__ = ["UploadedFile"]
```

- [ ] **Step 4: 实现 Mapper**

```python
# db/mappers.py
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
```

- [ ] **Step 5: 运行 Mapper 与全量测试**

Run: `uv run --cache-dir .uv-cache pytest tests/test_mappers.py -q`

Expected: `2 passed`。

Run: `uv run --cache-dir .uv-cache pytest tests -q`

Expected: `50 passed, 1 warning`。

- [ ] **Step 6: 提交**

`ash
git add db/models db/mappers.py models tests/test_mappers.py
git commit -m "refactor(db): 迁移ORM并增加领域映射器"
```

### Task 4: 四个 SQLAlchemy Repository 实现

**Files:**
- Create: `db/repositories/__init__.py`
- Create: `db/repositories/conversation.py`
- Create: `db/repositories/topic.py`
- Create: `db/repositories/memory.py`
- Create: `db/repositories/file.py`
- Test: `tests/test_repository_contracts.py`

**Interfaces:**
- Consumes: Task 2 的 Repository Protocol；Task 3 的 ORM 和 Mapper。
- Produces: `SqlAlchemyConversationRepository`、`SqlAlchemyTopicRepository`、`SqlAlchemyMemoryRepository`、`SqlAlchemyFileRepository`。

- [ ] **Step 1: 写 Repository 契约失败测试**

```python
# tests/test_repository_contracts.py
import inspect
from pathlib import Path

from db.repositories.conversation import SqlAlchemyConversationRepository
from db.repositories.file import SqlAlchemyFileRepository
from db.repositories.memory import SqlAlchemyMemoryRepository
from db.repositories.topic import SqlAlchemyTopicRepository


def test_repository_implementations_expose_required_methods():
    assert inspect.iscoroutinefunction(SqlAlchemyConversationRepository.add_turn)
    assert inspect.iscoroutinefunction(SqlAlchemyConversationRepository.get_recent_topic_messages)
    assert inspect.iscoroutinefunction(SqlAlchemyTopicRepository.switch)
    assert inspect.iscoroutinefunction(SqlAlchemyMemoryRepository.upsert)
    assert inspect.iscoroutinefunction(SqlAlchemyFileRepository.list_all)


def test_repositories_never_commit():
    root = Path(__file__).resolve().parents[1] / "db" / "repositories"
    for path in root.glob("*.py"):
        assert ".commit(" not in path.read_text(encoding="utf-8")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --cache-dir .uv-cache pytest tests/test_repository_contracts.py -q`

Expected: FAIL，报 `ModuleNotFoundError: No module named 'db.repositories'`。

- [ ] **Step 3: 实现会话与消息 Repository**

将 `db/conversation_repo.py` 的查询逻辑迁移到 `db/repositories/conversation.py`，删除 Topic/Memory 子仓储和 LangChain 消息转换，所有公开返回值改为领域对象。核心结构：

```python
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import db_conf
from db.mappers import to_conversation, to_message
from db.models.conversation import Conversation as ConversationModel
from db.models.conversation import Message as MessageModel
from domain.entities import Conversation, Message
from domain.enums import ScopeLabel


class SqlAlchemyConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: str, title: str) -> Conversation:
        row = ConversationModel(user_id=user_id, title=title)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return to_conversation(row)

    async def get(self, conversation_id: UUID) -> Conversation | None:
        row = await self.session.get(ConversationModel, conversation_id)
        return to_conversation(row) if row else None

    async def list_by_user(self, user_id: str, limit: int = 50, offset: int = 0) -> list[Conversation]:
        result = await self.session.execute(
            select(ConversationModel)
            .where(ConversationModel.user_id == user_id)
            .order_by(ConversationModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [to_conversation(row) for row in result.scalars().all()]

    async def delete(self, conversation_id: UUID) -> bool:
        row = await self.session.get(ConversationModel, conversation_id)
        if row is None:
            return False
        await self.session.delete(row)
        return True

    async def get_messages(self, conversation_id: UUID, limit: int = 100) -> list[Message]:
        result = await self.session.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
            .limit(limit)
        )
        return [to_message(row) for row in result.scalars().all()]

    async def get_recent_topic_messages(
        self,
        topic_id: UUID | None,
        *,
        max_turns: int | None = None,
        max_tokens: int | None = None,
    ) -> list[Message]:
        max_turns = max_turns or db_conf.get("topic_recent_turns", 2)
        max_tokens = max_tokens or db_conf.get("context_max_tokens", 2000)
        stmt = (
            select(MessageModel)
            .where(
                MessageModel.topic_id == topic_id,
                MessageModel.memory_eligible.is_(True),
                MessageModel.is_refusal.is_(False),
                MessageModel.scope_label != "OUT",
                MessageModel.turn_id.is_not(None),
            )
            .order_by(MessageModel.created_at.desc(), MessageModel.id.desc())
            .limit(max_turns * 4)
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())
        by_turn: dict[UUID, list[MessageModel]] = {}
        for record in records:
            by_turn.setdefault(record.turn_id, []).append(record)

        turns: list[list[MessageModel]] = []
        for turn_records in by_turn.values():
            turn_records.sort(key=lambda item: (item.created_at, item.id))
            roles = {item.role for item in turn_records}
            if {"human", "ai"} <= roles:
                turns.append([item for item in turn_records if item.role in {"human", "ai"}])
        turns.sort(key=lambda items: (items[0].created_at, items[0].id))

        selected: list[MessageModel] = []
        token_count = 0
        for turn in reversed(turns):
            turn_tokens = sum(self._estimate_tokens(item.content) for item in turn)
            if len(selected) >= max_turns * 2 or token_count + turn_tokens > max_tokens:
                break
            selected[0:0] = turn
            token_count += turn_tokens
        return [to_message(item) for item in selected]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
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
    ) -> tuple[Message, Message]:
        turn_id = uuid4()
        human = MessageModel(
            conversation_id=conversation_id,
            topic_id=topic_id,
            turn_id=turn_id,
            role="human",
            content=user_content,
            intent=intent,
            scope_label=scope_label.value,
            is_refusal=is_refusal,
            memory_eligible=memory_eligible,
        )
        assistant = MessageModel(
            conversation_id=conversation_id,
            topic_id=topic_id,
            turn_id=turn_id,
            role="ai",
            content=assistant_content,
            intent=intent,
            scope_label=scope_label.value,
            is_refusal=is_refusal,
            memory_eligible=memory_eligible,
        )
        self.session.add_all([human, assistant])
        await self.session.execute(
            update(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .values(updated_at=func.now())
        )
        await self.session.flush()
        return to_message(human), to_message(assistant)
```

`get_recent_topic_messages` 的实现必须原样保留旧 `db/conversation_repo.py:get_recent_topic_records` 的过滤条件、按 `turn_id` 分组、只保留 Human/AI 成对轮次、按时间排序和 Token 预算逻辑；唯一差异是构建查询时使用 `MessageModel`，返回前使用 `to_message`。

- [ ] **Step 4: 实现主题、记忆和文件 Repository**

`SqlAlchemyTopicRepository` 逐方法迁移 `db/topic_repo.py`，SQL 条件、排序、`flush()`、`refresh()` 和乐观锁 `expected_version` 不变，返回值统一改为 `to_topic(row)`。方法名把旧 `switch_topic` 改为端口名 `switch`：

```python
class SqlAlchemyTopicRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active(self, conversation_id: UUID) -> ConversationTopic | None:
        result = await self.session.execute(
            select(TopicModel)
            .where(TopicModel.conversation_id == conversation_id, TopicModel.status == "active")
            .order_by(TopicModel.updated_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return to_topic(row) if row else None

    async def switch(
        self,
        conversation_id: UUID,
        topic_label: str,
        *,
        intent: str | None = None,
        scope_label: ScopeLabel = ScopeLabel.IN,
        confidence: float = 0.0,
    ) -> ConversationTopic:
        active = await self.get_active(conversation_id)
        if active is not None:
            await self.archive(active.id)
        return await self.create(
            conversation_id,
            topic_label,
            intent=intent,
            scope_label=scope_label,
            confidence=confidence,
        )
```

`SqlAlchemyMemoryRepository` 逐方法迁移 `db/memory_repo.py`，`list_active`、`upsert`、`delete_one`、`delete_all` 的 SQL 和排序不变，返回值使用 `to_memory_item`。

`SqlAlchemyFileRepository` 逐方法迁移 `db/file_repo.py`：

- `get_by_md5` 返回 `to_uploaded_file`
- `save(file_id: UUID, filename: str, md5_hex: str, file_size: int)` 使用 `UploadedFileModel(id=file_id, filename=filename, md5_hex=md5_hex, size=file_size)`，返回领域 `UploadedFile`
- `list_all` 保留 `REPLACE(uf.id::TEXT, '-', '') = (lpe.cmetadata ->> 'file_id')` JOIN，返回 `to_file_summary(row)`
- `delete_by_id` 参数改为 `UUID`
- `delete_vector_embeddings` 重命名为 `delete_index_records`，SQL 文本保持不变

`db/repositories/__init__.py` 统一导出四个类：

```python
from db.repositories.conversation import SqlAlchemyConversationRepository
from db.repositories.file import SqlAlchemyFileRepository
from db.repositories.memory import SqlAlchemyMemoryRepository
from db.repositories.topic import SqlAlchemyTopicRepository

__all__ = [
    "SqlAlchemyConversationRepository",
    "SqlAlchemyFileRepository",
    "SqlAlchemyMemoryRepository",
    "SqlAlchemyTopicRepository",
]
```

- [ ] **Step 5: 运行 Repository 测试和全量测试**

Run: `uv run --cache-dir .uv-cache pytest tests/test_repository_contracts.py -q`

Expected: `2 passed`。

Run: `uv run --cache-dir .uv-cache pytest tests -q`

Expected: `52 passed, 1 warning`。

- [ ] **Step 6: 提交**

`ash
git add db/repositories tests/test_repository_contracts.py
git commit -m "refactor(db): 拆分并实现领域仓储端口"
```

### Task 5: AI/RAG 适配器迁移到端口

**Files:**
- Move: `services/topic_router.py` -> `agent/topic_router.py`
- Move: `services/summary_service.py` -> `agent/summary_agent.py`
- Move: `services/guard_service.py` -> `agent/guard_agent.py`
- Create: `agent/memory_agent.py`
- Create: `agent/chat_agent.py`
- Modify: `rag/rag_service.py`
- Modify: `tests/test_topic_router.py`
- Modify: `tests/test_chat_service_memory.py` 中 TopicDecision 类型引用
- Create temporary compatibility shims: `services/topic_router.py`, `services/summary_service.py`, `services/guard_service.py`
- Test: `tests/test_ai_adapters.py`

**Interfaces:**
- Consumes: Task 1 的领域类型、Task 2 的端口。
- Produces: `get_topic_router()`、`get_summary_agent()`、`get_guard_agent()`、`get_memory_extractor()`、`get_chat_agent()`；`ChatAgent.execute()` 返回 `ChatAnswer`。

- [ ] **Step 1: 写适配器失败测试**

```python
# tests/test_ai_adapters.py
from domain.decisions import ChatAnswer, MemoryCandidate, TopicDecision
from domain.entities import ConversationTopic
from domain.enums import ScopeLabel, TopicAction, TopicStatus
from agent.summary_agent import SummaryAgent
from agent.topic_router import TopicRouter


class FakeModel:
    def __init__(self, raw):
        self.raw = raw

    def invoke(self, _messages):
        return type("Response", (), {"content": self.raw})()


def test_topic_router_returns_domain_decision():
    raw = '{"action":"OUT_OF_SCOPE","scope":"OUT","confidence":0.9}'
    decision = TopicRouter(model=FakeModel(raw)).route("股票")
    assert isinstance(decision, TopicDecision)
    assert decision.action == TopicAction.OUT_OF_SCOPE
    assert decision.scope == ScopeLabel.OUT


def test_summary_agent_returns_raw_non_json_text():
    topic = ConversationTopic(
        id=__import__("uuid").uuid4(),
        conversation_id=__import__("uuid").uuid4(),
        topic_label="T恤",
        summary="",
        last_intent=None,
        scope_label=ScopeLabel.IN,
        confidence=0.0,
        status="active",
        summary_version=0,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    assert SummaryAgent(model=FakeModel("not-json")).summarize(topic, "问", "答") == "not-json"


def test_chat_answer_type_has_sources():
    value = ChatAnswer(answer="ok", sources=["a.txt"])
    assert value.sources == ["a.txt"]


def test_memory_candidate_type_is_stable():
    value = MemoryCandidate(memory_key="size", content="L", confidence=0.9)
    assert value.memory_key == "size"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --cache-dir .uv-cache pytest tests/test_ai_adapters.py -q`

Expected: FAIL，报 `ModuleNotFoundError: No module named 'agent.summary_agent'` 或 `agent.topic_router`。

- [ ] **Step 3: 迁移 TopicRouter**

```powershell
git mv services/topic_router.py agent/topic_router.py
git mv services/summary_service.py agent/summary_agent.py
git mv services/guard_service.py agent/guard_agent.py
```

迁移期保留旧导入路径，避免 Task 7 之前 `services/chat_service.py` 断裂：

```python
# services/topic_router.py
from agent.topic_router import TopicRouter, get_topic_router

__all__ = ["TopicRouter", "get_topic_router"]
```

```python
# services/summary_service.py
from agent.summary_agent import SummaryAgent as SummaryService
from agent.summary_agent import get_summary_agent as get_summary_service

__all__ = ["SummaryService", "get_summary_service"]
```

```python
# services/guard_service.py
from agent.guard_agent import GuardAgent as GuardService
from agent.guard_agent import get_guard_agent as get_guard_service

__all__ = ["GuardService", "get_guard_service"]
```

`agent/topic_router.py` 删除 `schemas.topic` 和 ORM 依赖，改为 `domain.entities`、`domain.decisions`、`domain.enums`。`_parse` 中：

```python
action = TopicAction(action) if action in {item.value for item in TopicAction} else TopicAction.CONTINUE
scope = ScopeLabel.OUT if str(obj.get("scope", "IN")).upper() == "OUT" else ScopeLabel.IN
if scope == ScopeLabel.OUT:
    action = TopicAction.OUT_OF_SCOPE
segments = [
    TopicSegment(
        query=str(item.get("query", "") or "").strip(),
        scope=ScopeLabel.OUT if str(item.get("scope", "IN")).upper() == "OUT" else ScopeLabel.IN,
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
```

`_fallback` 返回 `dataclass` 时必须使用 `TopicAction.CONTINUE`、`TopicAction.CLARIFY` 和 `ScopeLabel.IN`，其他文案保持不变。函数名仍为 `get_topic_router()`。

- [ ] **Step 4: 迁移 Summary 与 Guard 适配器**

`agent/summary_agent.py`：

```python
import json
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage

from core.logger import logger
from domain.entities import ConversationTopic
from rag.model.factory import get_rewrite_model
from utils.prompt_loader import load_summary_prompt


def _content(response) -> str:
    value = getattr(response, "content", response)
    if isinstance(value, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in value)
    return str(value)


@lru_cache(maxsize=1)
def get_summary_agent() -> "SummaryAgent":
    return SummaryAgent()


class SummaryAgent:
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
            logger.warning("[SummaryAgent] 摘要更新失败，保留旧摘要: %s", exc)
            return None
```

`agent/guard_agent.py` 将 `get_guard_service` 改名为 `get_guard_agent`，类名改为 `GuardAgent`；解析正则、L0/L3 提示词、默认放行和 `refusal_text` 语义保持不变。

- [ ] **Step 5: 抽离 MemoryExtractor 并新增 ChatAgent**

`agent/memory_agent.py`：

```python
import json
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage

from core.logger import logger
from domain.decisions import MemoryCandidate
from rag.model.factory import get_rewrite_model
from utils.prompt_loader import load_memory_prompt


def _content(response) -> str:
    value = getattr(response, "content", response)
    if isinstance(value, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in value)
    return str(value)


@lru_cache(maxsize=1)
def get_memory_extractor() -> "MemoryExtractor":
    return MemoryExtractor()


class MemoryExtractor:
    def __init__(self, model=None):
        self.model = model or get_rewrite_model()
        self.prompt = load_memory_prompt()

    def extract(self, user_message: str) -> list[MemoryCandidate]:
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
                    MemoryCandidate(
                        memory_key=str(item.get("memory_key", "")),
                        content=str(item.get("content", "")),
                        confidence=float(item.get("confidence", 0)),
                        expires_at=item.get("expires_at"),
                    )
                    for item in data
                    if isinstance(item, dict)
                ]
        except Exception as exc:
            logger.warning("[MemoryExtractor] 长期记忆提取失败: %s", exc)
        return []
```

`rag/rag_service.py` 增加 `reset_sources_collection(token)`，只重置 `_sources_ctx`。

`agent/chat_agent.py`：

```python
@lru_cache(maxsize=1)
def get_chat_agent() -> "ChatAgent":
    return ChatAgent()


class ChatAgent:
    def __init__(self, agent=None):
        from agent.react_agent import ReactAgent

        self.agent = agent or ReactAgent()

    async def execute(self, query: str, context: str, topic_label: str) -> ChatAnswer:
        source_token = start_sources_collection()
        topic_token = start_topic_context(topic_label)
        try:
            answer = await self.agent.aexecute(query, context)
            return ChatAnswer(answer=answer, sources=list(collect_sources()))
        finally:
            reset_sources_collection(source_token)
            reset_topic_context(topic_token)
```

- [ ] **Step 6: 更新现有 TopicRouter 测试并运行**

将 `tests/test_topic_router.py` 的导入改为：

```python
from agent.topic_router import TopicRouter
from domain.entities import ConversationTopic, Message
```

断言字符串可保持不变，因为 `str Enum` 与字符串相等。运行：

Run: `uv run --cache-dir .uv-cache pytest tests/test_ai_adapters.py tests/test_topic_router.py -q`

Expected: 全部 PASS。

Run: `uv run --cache-dir .uv-cache pytest tests -q`

Expected: `56 passed, 1 warning`。

- [ ] **Step 7: 提交**

```bash
git add agent rag/rag_service.py services/topic_router.py services/summary_service.py services/guard_service.py tests/test_ai_adapters.py tests/test_topic_router.py
git commit -m "refactor(agent): 将AI能力迁移为领域端口适配器"
```

### Task 6: 会话、主题、记忆应用服务与 ContextBuilder

**Files:**
- Create: `services/conversation_service.py`
- Create: `services/topic_service.py`
- Rewrite: `services/memory_service.py`
- Modify: `services/context_builder.py`
- Modify: `tests/test_context_builder.py`
- Modify: `tests/test_memory_service.py`
- Test: `tests/test_app_services.py`

**Interfaces:**
- Consumes: Task 2 的 Repository/Extractor 端口，Task 1 的领域实体。
- Produces: `ConversationService`、`TopicService`、新的 `MemoryService` 构造函数和 `ContextBuilder.build()` 领域签名。

- [ ] **Step 1: 写应用服务失败测试**

```python
# tests/test_app_services.py
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from domain.entities import Conversation, MemoryItem
from domain.errors import TopicNotFoundError
from services.conversation_service import ConversationService
from services.memory_service import MemoryService
from services.topic_service import TopicService


class FakeConversationRepo:
    def __init__(self):
        self.items = {}

    async def create(self, user_id, title):
        now = datetime.now(timezone.utc)
        item = Conversation(uuid4(), user_id, title, now, now)
        self.items[item.id] = item
        return item

    async def get(self, conversation_id):
        return self.items.get(conversation_id)

    async def list_by_user(self, user_id, limit=50, offset=0):
        return [item for item in self.items.values() if item.user_id == user_id]

    async def delete(self, conversation_id):
        return self.items.pop(conversation_id, None) is not None

    async def get_messages(self, conversation_id, limit=100):
        return []


class FakeTopicRepo:
    def __init__(self):
        self.archived = []

    async def create(self, conversation_id, topic_label="服装咨询", **kwargs):
        from domain.entities import ConversationTopic
        from domain.enums import ScopeLabel, TopicStatus

        now = datetime.now(timezone.utc)
        return ConversationTopic(
            uuid4(), conversation_id, topic_label, "", kwargs.get("intent"),
            ScopeLabel.IN, 0.0, TopicStatus.ACTIVE, 0, now, now,
        )

    async def archive(self, topic_id):
        self.archived.append(topic_id)
        return True

    async def get(self, conversation_id, topic_id):
        return None


class FakeMemoryRepo:
    async def list_active(self, user_id, limit=12):
        now = datetime.now(timezone.utc)
        return [
            MemoryItem(
                uuid4(), user_id, "preference", "size", "常用尺码 L", None,
                0.95, None, "active", now, now,
            )
        ]

    async def delete_one(self, user_id, memory_id):
        return True

    async def delete_all(self, user_id):
        return 2


def test_conversation_service_creates_default_topic():
    async def scenario():
        conversations = FakeConversationRepo()
        topics = FakeTopicRepo()
        service = ConversationService(conversations, topics)
        item = await service.create("u1", "新对话")
        assert (await service.list("u1"))[0].id == item.id
    asyncio.run(scenario())


def test_topic_service_maps_missing_topic_to_domain_error():
    async def scenario():
        service = TopicService(FakeConversationRepo(), FakeTopicRepo())
        try:
            await service.get(uuid4(), uuid4())
        except TopicNotFoundError:
            return
        raise AssertionError("应抛出 TopicNotFoundError")
    asyncio.run(scenario())


def test_memory_service_lists_and_deletes():
    async def scenario():
        service = MemoryService(FakeMemoryRepo())
        memories = await service.list_active("u1")
        assert memories[0].memory_key == "size"
        assert await service.delete_all("u1") == 2
    asyncio.run(scenario())
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --cache-dir .uv-cache pytest tests/test_app_services.py -q`

Expected: FAIL，报 `ModuleNotFoundError: No module named 'services.conversation_service'`。

- [ ] **Step 3: 实现 ConversationService 和 TopicService**

```python
# services/conversation_service.py
from uuid import UUID

from domain.entities import Conversation, Message
from domain.ports import ConversationRepositoryPort, TopicRepositoryPort


class ConversationService:
    def __init__(self, conversations: ConversationRepositoryPort, topics: TopicRepositoryPort):
        self.conversations = conversations
        self.topics = topics

    async def create(self, user_id: str, title: str, *, create_topic: bool = True) -> Conversation:
        item = await self.conversations.create(user_id, title)
        if create_topic:
            await self.topics.create(item.id)
        return item

    async def list(self, user_id: str) -> list[Conversation]:
        return await self.conversations.list_by_user(user_id)

    async def get_messages(self, conversation_id: UUID) -> list[Message]:
        return await self.conversations.get_messages(conversation_id)

    async def delete(self, conversation_id: UUID) -> bool:
        return await self.conversations.delete(conversation_id)
```

```python
# services/topic_service.py
from uuid import UUID

from domain.entities import ConversationTopic
from domain.errors import ConversationNotFoundError, TopicNotFoundError
from domain.ports import ConversationRepositoryPort, TopicRepositoryPort


class TopicService:
    def __init__(self, conversations: ConversationRepositoryPort, topics: TopicRepositoryPort):
        self.conversations = conversations
        self.topics = topics

    async def list(self, conversation_id: UUID) -> list[ConversationTopic]:
        if await self.conversations.get(conversation_id) is None:
            raise ConversationNotFoundError(str(conversation_id))
        return await self.topics.list(conversation_id)

    async def get(self, conversation_id: UUID, topic_id: UUID) -> ConversationTopic:
        item = await self.topics.get(conversation_id, topic_id)
        if item is None:
            raise TopicNotFoundError(str(topic_id))
        return item

    async def archive(self, conversation_id: UUID, topic_id: UUID) -> None:
        await self.get(conversation_id, topic_id)
        await self.topics.archive(topic_id)
```

- [ ] **Step 4: 重写 MemoryService 并迁移 ContextBuilder 类型**

`services/memory_service.py` 保留 `_ALLOWED_KEYS`、`_INTENT_KEYWORDS`、`_SHOPPING_KEYWORDS`、`_SHOPPING_INTENTS` 和 `_is_explicit`。构造函数改为：

```python
class MemoryService:
    def __init__(self, repository: MemoryRepositoryPort, extractor: MemoryExtractorPort | None = None):
        self.repository = repository
        self.extractor = extractor
        self.threshold = db_conf.get("memory_confidence_threshold", 0.8)

    async def list_active(self, user_id: str) -> list[MemoryItem]:
        return await self.repository.list_active(user_id, db_conf.get("memory_max_items", 12))

    async def list_for_prompt(self, user_id: str) -> list[MemoryItem]:
        if not user_id or user_id == "anonymous":
            return []
        return await self.list_active(user_id)

    async def delete_one(self, user_id: str, memory_id: UUID) -> bool:
        return await self.repository.delete_one(user_id, memory_id)

    async def delete_all(self, user_id: str) -> int:
        return await self.repository.delete_all(user_id)

    async def extract_and_save(self, *, user_id: str, user_message: str, source_message: Message | None) -> None:
        if not user_id or user_id == "anonymous" or self.extractor is None:
            return
        candidates = await asyncio.to_thread(self.extractor.extract, user_message)
        for candidate in candidates:
            if (
                candidate.memory_key not in _ALLOWED_KEYS
                or candidate.confidence < self.threshold
                or not self._is_explicit(user_message, candidate.memory_key)
            ):
                continue
            expires_at = None
            if candidate.expires_at:
                try:
                    expires_at = datetime.fromisoformat(candidate.expires_at)
                except ValueError:
                    expires_at = None
            await self.repository.upsert(
                user_id=user_id,
                memory_type="preference",
                memory_key=candidate.memory_key,
                content=candidate.content[:500],
                source_message_id=source_message.id if source_message else None,
                confidence=candidate.confidence,
                expires_at=expires_at,
            )
```

`select_for_query(memories: list[MemoryItem], query: str, intent: str | None = None) -> list[MemoryItem]` 的筛选规则保持原样。`services/context_builder.py` 只把 ORM 导入改为 `domain.entities`，把 `status == "active"` 改为兼容 `item.status == "active"`，把 `scope_label == "OUT"` 改为 `item.scope_label == ScopeLabel.OUT`，其余算法不动。

- [ ] **Step 5: 更新现有领域测试**

`tests/test_context_builder.py` 和 `tests/test_memory_service.py` 改为使用 `domain.entities`，并注入 fake `MemoryExtractorPort`；删除对 ORM 构造函数的依赖。运行：

Run: `uv run --cache-dir .uv-cache pytest tests/test_app_services.py tests/test_context_builder.py tests/test_memory_service.py -q`

Expected: 全部 PASS。

Run: `uv run --cache-dir .uv-cache pytest tests -q`

Expected: `59 passed, 1 warning`。

- [ ] **Step 6: 提交**

`ash
git add services tests/test_app_services.py tests/test_context_builder.py tests/test_memory_service.py
git commit -m "refactor(services): 增加会话主题记忆应用服务"
```

### Task 7: ChatService、API 组合根与聊天路由迁移

**Files:**
- Modify: `services/chat_service.py`
- Create: `api/dependencies.py`
- Modify: `api/chat.py`
- Modify: `tests/test_chat_api.py`
- Modify: `tests/test_topic_api.py`
- Modify: `tests/test_chat_service_memory.py`
- Test: `tests/test_api_dependencies.py`

**Interfaces:**
- Consumes: Task 2 端口、Task 4 Repository、Task 5 适配器、Task 6 应用服务。
- Produces: `ChatService` 新构造函数；`get_conversation_service`、`get_topic_service`、`get_memory_service`、`get_chat_service`。

- [ ] **Step 1: 写依赖与 ChatService 构造器失败测试**

```python
# tests/test_api_dependencies.py
from api.dependencies import get_chat_service, get_conversation_service
from db.session import get_db
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_dependencies_are_fastapi_callables():
    assert callable(get_chat_service)
    assert callable(get_conversation_service)


def test_app_import_registers_routes():
    from main import app
    paths = {route.path for route in app.routes}
    assert "/api/chat/" in paths
    assert "/api/conversations" in paths
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --cache-dir .uv-cache pytest tests/test_api_dependencies.py -q`

Expected: FAIL，报 `ModuleNotFoundError: No module named 'api.dependencies'`。

- [ ] **Step 3: 改写 ChatService 构造函数和依赖注入**

`services/chat_service.py` 删除所有 `db`、`schemas`、`rag` 和具体 Repository 导入。构造函数：

```python
class ChatService:
    def __init__(
        self,
        *,
        conversations: ConversationRepositoryPort,
        topics: TopicRepositoryPort,
        memory_service: MemoryService | None,
        context_builder: ContextBuilder,
        topic_router: TopicClassifierPort | None,
        guard: GuardPort,
        chat_agent: ChatAgentPort,
        summary_agent: SummaryGeneratorPort | None,
    ):
        self.conversations = conversations
        self.topics = topics
        self.memory_service = memory_service
        self.context_builder = context_builder
        self.topic_router = topic_router
        self.guard = guard
        self.chat_agent = chat_agent
        self.summary_agent = summary_agent
        self.memory_enabled = bool(db_conf.get("conversation_memory_enabled", True))
        self.router_enabled = bool(db_conf.get("topic_router_enabled", True))
        self.long_term_memory_enabled = bool(db_conf.get("long_term_memory_enabled", True))
        self.summary_enabled = bool(db_conf.get("summary_enabled", True))
```

`process_message()`、`_route()`、`_prepare_topic()`、`_handle_clarify()`、`_handle_out_of_scope()`、`_handle_refusal()` 和 `_update_summary()` 只做以下机械替换：

- `self.store.get_conversation` → `self.conversations.get`
- `self.store.topics.*` → `self.topics.*`
- `self.store.get_recent_topic_records` → `self.conversations.get_recent_topic_messages`
- `self.store.add_turn` → `self.conversations.add_turn`
- `decision.action == "X"` → `decision.action == TopicAction.X`
- `decision.scope == "OUT"` → `decision.scope == ScopeLabel.OUT`
- `get_guard_service()` → `self.guard`
- `get_summary_service()` → `self.summary_agent`
- `self.context_builder.build()` 参数类型改为领域实体

`_execute_agent()` 改为：

```python
async def _execute_agent(self, query: str, context: str, topic_label: str) -> tuple[str, list[str]]:
    result = await self.chat_agent.execute(query, context, topic_label)
    return result.answer, result.sources
```

删除 `_get_react_agent`、`_sources_ctx`、`start_sources_collection`、`collect_sources`、`start_topic_context` 和 `reset_topic_context` 的导入与使用。

- [ ] **Step 4: 创建 API 组合根**

```python
# api/dependencies.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent.chat_agent import get_chat_agent
from agent.guard_agent import get_guard_agent
from agent.memory_agent import get_memory_extractor
from agent.summary_agent import get_summary_agent
from agent.topic_router import get_topic_router
from core.config import db_conf
from db.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMemoryRepository,
    SqlAlchemyTopicRepository,
)
from db.session import get_db
from services.chat_service import ChatService
from services.context_builder import ContextBuilder
from services.conversation_service import ConversationService
from services.memory_service import MemoryService
from services.topic_service import TopicService


def _repositories(db: AsyncSession):
    return (
        SqlAlchemyConversationRepository(db),
        SqlAlchemyTopicRepository(db),
        SqlAlchemyMemoryRepository(db),
    )


def get_conversation_service(db: AsyncSession = Depends(get_db)) -> ConversationService:
    conversations, topics, _ = _repositories(db)
    return ConversationService(conversations, topics)


def get_topic_service(db: AsyncSession = Depends(get_db)) -> TopicService:
    conversations, topics, _ = _repositories(db)
    return TopicService(conversations, topics)


def get_memory_service(db: AsyncSession = Depends(get_db)) -> MemoryService:
    _, _, memories = _repositories(db)
    enabled = bool(db_conf.get("conversation_memory_enabled", True)) and bool(
        db_conf.get("long_term_memory_enabled", True)
    )
    extractor = get_memory_extractor() if enabled else None
    return MemoryService(memories, extractor)


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    conversations, topics, memories = _repositories(db)
    memory_enabled = bool(db_conf.get("conversation_memory_enabled", True))
    long_term_enabled = bool(db_conf.get("long_term_memory_enabled", True))
    memory_service = (
        MemoryService(memories, get_memory_extractor())
        if memory_enabled and long_term_enabled
        else None
    )
    return ChatService(
        conversations=conversations,
        topics=topics,
        memory_service=memory_service,
        context_builder=ContextBuilder(),
        topic_router=get_topic_router() if db_conf.get("topic_router_enabled", True) else None,
        guard=get_guard_agent(),
        chat_agent=get_chat_agent(),
        summary_agent=get_summary_agent() if db_conf.get("summary_enabled", True) else None,
    )

```

- [ ] **Step 5: 迁移 chat API**

删除 `api/chat.py` 的 `sqlalchemy`、`db.session`、Repository 和 `ChatService` 直接导入，路由签名改为：

```python
@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    user_id: str = "anonymous",
    service: ConversationService = Depends(get_conversation_service),
):
    conversations = await service.list(user_id)
    return ConversationListResponse(
        conversations=[
            ConversationListItem(
                conversation_id=str(item.id),
                title=item.title,
                created_at=item.created_at.isoformat(),
                updated_at=item.updated_at.isoformat(),
                message_count=0,
            )
            for item in conversations
        ]
    )
```

创建会话路由调用 `service.create(..., create_topic=db_conf.get("conversation_memory_enabled", True))`。Chat、主题、记忆、删除会话路由按同样方式改为调用依赖注入的 Service。领域错误映射：

```python
except ConversationNotFoundError:
    raise HTTPException(status_code=404, detail="对话不存在")
```

`_topic_item` 和 `_memory_item` 保留，但输入类型改为领域实体。`ChatResponse` 仍兼容 `hasattr(result, "answer")` 和旧三元组返回值，直到所有测试更新后删除兼容分支。

- [ ] **Step 6: 更新聊天、主题和 ChatService 测试**

`tests/test_chat_api.py`、`tests/test_topic_api.py` 改为 override FastAPI dependency（`app.dependency_overrides`），不再 patch `api.chat.ConversationRepository`。

`tests/test_chat_service_memory.py` 的 `make_service(store)` 改为构造 fake `conversations`、`topics`、`MemoryService`、`ContextBuilder`、`TopicClassifierPort`、`GuardPort`、`ChatAgentPort`、`SummaryGeneratorPort`。保留所有断言和场景，仅把 ORM `SimpleNamespace` 改为领域 dataclass。

- [ ] **Step 7: 运行 API 与全量测试**

Run: `uv run --cache-dir .uv-cache pytest tests/test_api_dependencies.py tests/test_chat_api.py tests/test_topic_api.py tests/test_chat_service_memory.py -q`

Expected: 全部 PASS。

Run: `uv run --cache-dir .uv-cache pytest tests -q`

Expected: `61 passed, 1 warning`。

- [ ] **Step 8: 提交**

```bash
git add services/chat_service.py api/dependencies.py api/chat.py tests/test_api_dependencies.py tests/test_chat_api.py tests/test_topic_api.py tests/test_chat_service_memory.py
git commit -m "refactor(api): 通过依赖注入迁移聊天路由"
```

### Task 8: DocumentService 与文件 API 迁移

**Files:**
- Create: `services/document_service.py`
- Modify: `api/documents.py`
- Modify: `api/dependencies.py`
- Test: `tests/test_document_service.py`

**Interfaces:**
- Consumes: `FileRepositoryPort`、`DocumentIndexPort`、`AsyncDocumentReader`、领域文件错误。
- Produces: `DocumentService.upload()`、`DocumentService.list_all()`、`DocumentService.delete()`。

- [ ] **Step 1: 写 DocumentService 失败测试**

```python
# tests/test_document_service.py
import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from domain.entities import FileSummary, UploadedFile
from domain.errors import DuplicateDocumentError


class Stream:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    async def read(self, size):
        return self.chunks.pop(0) if self.chunks else b""


class FakeFileRepo:
    def __init__(self):
        self.saved = []

    async def get_by_md5(self, md5_hex):
        return None

    async def save(self, file_id, filename, md5_hex, file_size):
        now = datetime.now(timezone.utc)
        item = UploadedFile(file_id, filename, md5_hex, file_size, now)
        self.saved.append(item)
        return item

    async def list_all(self):
        return [FileSummary(uuid4(), "a.txt", 1, 2)]

    async def delete_by_id(self, file_id):
        return True

    async def delete_index_records(self, file_id):
        return 2


class FakeIndex:
    def __init__(self):
        self.deleted = []

    def load_document(self, file_id, target_path):
        return [f"{file_id}-chunk0"]

    def delete_documents(self, ids):
        self.deleted.extend(ids)


def test_document_service_uploads_and_returns_chunks(tmp_path, monkeypatch):
    async def scenario():
        repo = FakeFileRepo()
        index = FakeIndex()
        service = DocumentService(repo, index, data_dir=str(tmp_path), allowed_types={"txt"})
        result = await service.upload("a.txt", Stream([b"hello"]))
        assert result.file.filename == "a.txt"
        assert result.chunks == [f"{result.file.id.hex}-chunk0"]
    asyncio.run(scenario())
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --cache-dir .uv-cache pytest tests/test_document_service.py -q`

Expected: FAIL，报 `ModuleNotFoundError: No module named 'services.document_service'`。

- [ ] **Step 3: 实现 DocumentService**

`services/document_service.py` 必须逐段迁移 `api/documents.py` 的现有逻辑：

1. 校验扩展名，失败抛 `UnsupportedDocumentTypeError`；
2. 使用 `file_id = uuid4()` 生成 UUID，向量 ID 使用 `file_id.hex`，临时文件命名为 `{file_id.hex}.{extension}`；
3. `while chunk := await stream.read(8192)` 写文件并计算 MD5；
4. 空文件抛 `EmptyDocumentError`；
5. `get_by_md5` 命中抛 `DuplicateDocumentError`；
6. `await asyncio.to_thread(self.index.load_document, file_id.hex, str(temp_path))`，返回空抛 `DocumentIndexError`；
7. 保存元数据，任何异常都执行 `await asyncio.to_thread(self.index.delete_documents, added_ids)` 后继续抛出；
8. `finally` 删除临时文件；
9. 返回 `DocumentUploadResult(file=item, chunks=added_ids)`。

公开签名：

```python
import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from core.config import pg_conf
from core.paths import get_abs_path
from core.validators import validate_file_extension
from domain.entities import FileSummary, UploadedFile
from domain.errors import (
    DocumentIndexError,
    DocumentNotFoundError,
    DuplicateDocumentError,
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
)
from domain.ports import AsyncDocumentReader, DocumentIndexPort, FileRepositoryPort


@dataclass(slots=True)
class DocumentUploadResult:
    file: UploadedFile
    chunks: list[str]


class DocumentService:
    def __init__(
        self,
        files: FileRepositoryPort,
        index: DocumentIndexPort,
        *,
        data_dir: str | None = None,
        allowed_types: set[str] | None = None,
    ):
        self.files = files
        self.index = index
        self.data_dir = data_dir or get_abs_path(pg_conf["data_path"])
        self.allowed_types = allowed_types or {
            item.lower().lstrip(".") for item in pg_conf.get("allow_knowledge_file_type", [])
        }

    async def upload(self, filename: str, stream: AsyncDocumentReader) -> DocumentUploadResult:
        if not filename:
            raise UnsupportedDocumentTypeError("未检测到上传文件名")
        try:
            extension = validate_file_extension(filename, self.allowed_types)
        except ValueError as exc:
            raise UnsupportedDocumentTypeError(str(exc)) from exc

        data_dir = Path(self.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        file_id = uuid4()
        index_file_id = file_id.hex
        temp_path = data_dir / f"{index_file_id}.{extension}"
        md5_hash = hashlib.md5()
        file_size = 0
        added_ids: list[str] = []
        try:
            with temp_path.open("wb") as target:
                while chunk := await stream.read(8192):
                    target.write(chunk)
                    md5_hash.update(chunk)
                    file_size += len(chunk)

            if file_size == 0:
                raise EmptyDocumentError("上传文件为空")

            file_md5_hex = md5_hash.hexdigest()
            if await self.files.get_by_md5(file_md5_hex) is not None:
                raise DuplicateDocumentError("文件已存在于向量库中！")

            added_ids = await asyncio.to_thread(
                self.index.load_document,
                index_file_id,
                str(temp_path),
            )
            if not added_ids:
                raise DocumentIndexError("文件解析、切分并写入向量库失败")

            try:
                item = await self.files.save(
                    file_id=file_id,
                    filename=filename,
                    md5_hex=file_md5_hex,
                    file_size=file_size // 1024,
                )
            except Exception:
                await asyncio.to_thread(self.index.delete_documents, added_ids)
                raise
            return DocumentUploadResult(file=item, chunks=added_ids)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    async def list_all(self) -> list[FileSummary]:
        return await self.files.list_all()

    async def delete(self, file_id: UUID) -> None:
        deleted = await self.files.delete_by_id(file_id)
        if not deleted:
            raise DocumentNotFoundError(str(file_id))
        await self.files.delete_index_records(file_id.hex)
```

`delete()` 在记录不存在时抛 `DocumentNotFoundError`；删除记录后调用 `files.delete_index_records(file_id.hex)`。

- [ ] **Step 4: 注册 DocumentService 依赖**

在 `api/dependencies.py` 的 Repository 导入中加入 `SqlAlchemyFileRepository`，并追加：

```python
from rag.vector_store import VectorStoreService
from services.document_service import DocumentService


def get_document_service(db: AsyncSession = Depends(get_db)) -> DocumentService:
    return DocumentService(
        SqlAlchemyFileRepository(db),
        VectorStoreService(),
    )
```

- [ ] **Step 5: 迁移文件 API**

`api/documents.py` 删除 `asyncio`、`os`、`uuid`、`hashlib`、Repository、VectorStore 和配置导入，只保留 UploadFile 路由：

```python
@router.post("/upload")
async def upload_and_split(
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
):
    try:
        result = await service.upload(file.filename or "", file)
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except EmptyDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DuplicateDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DocumentIndexError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await file.close()
    return {
        "message": "文件解析、切分并写入向量库成功",
        "filename": result.file.filename,
        "chunks": result.chunks,
        "file_id": str(result.file.id),
    }
```

列表和删除路由分别调用 `service.list_all()` 与 `service.delete(uuid)`；非法 UUID 保持 400，记录不存在映射为 404 `文件记录不存在`。

- [ ] **Step 6: 运行文件与全量测试**

Run: `uv run --cache-dir .uv-cache pytest tests/test_document_service.py -q`

Expected: PASS。

Run: `uv run --cache-dir .uv-cache pytest tests -q`

Expected: `62 passed, 1 warning`。

- [ ] **Step 7: 提交**

```bash
git add services/document_service.py api/documents.py tests/test_document_service.py
git commit -m "refactor(documents): 将文件流程迁移到应用服务"
```

### Task 9: 删除兼容层、同步文档并完成最终验收

**Files:**
- Delete: `models/` compatibility package
- Delete: `db/conversation_repo.py`
- Delete: `db/topic_repo.py`
- Delete: `db/memory_repo.py`
- Delete: `db/file_repo.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `changelog.md`
- Modify: `docs/superpowers/specs/2026-09-22-backend-domain-layering-design.md`
- Test: `tests/test_architecture_boundaries.py`

**Interfaces:**
- Consumes: Task 1-8 的所有新模块。
- Produces: 最终无兼容转发的分层架构。

- [ ] **Step 1: 写架构边界失败测试**

```python
# tests/test_architecture_boundaries.py
import ast
from pathlib import Path


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module.split(".")[0])
    return result


def test_services_do_not_import_infrastructure_or_api():
    forbidden = {"api", "db", "fastapi", "sqlalchemy", "agent", "rag"}
    root = Path(__file__).resolve().parents[1] / "services"
    for path in root.glob("*.py"):
        assert not (_imports(path) & forbidden), path.name


def test_api_does_not_import_repositories_or_orm():
    root = Path(__file__).resolve().parents[1] / "api"
    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "db.repositories" not in source or path.name == "dependencies.py"
        assert "db.models" not in source


def test_old_repository_modules_are_removed():
    root = Path(__file__).resolve().parents[1] / "db"
    assert not (root / "conversation_repo.py").exists()
    assert not (root / "topic_repo.py").exists()
    assert not (root / "memory_repo.py").exists()
    assert not (root / "file_repo.py").exists()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --cache-dir .uv-cache pytest tests/test_architecture_boundaries.py -q`

Expected: FAIL，说明旧模块仍存在。

- [ ] **Step 3: 删除兼容层并修正规格接口签名**

```powershell
git rm -r models
git rm db/conversation_repo.py db/topic_repo.py db/memory_repo.py db/file_repo.py
```

校验规格中已经使用以下签名；若不一致则修正为：

```text
- `ChatAgentPort.execute(query, context, topic_label) -> ChatAnswer`
```

该签名是保留 `topic_label` 驱动的 Query Rewrite 和请求级 sources 收集所必需，行为不变。

- [ ] **Step 4: 更新文档**

README 的项目结构改为最终 `domain/`、`db/models/`、`db/repositories/`、`api/dependencies.py` 结构，并注明：

- `api` 只处理 HTTP；
- `services` 只编排用例；
- `domain` 无框架依赖；
- `db` 实现 Repository 端口；
- 外部接口、表结构和配置未变化。

AGENTS.md 增加同样的依赖规则和禁止事项，特别保留“Repository 不 commit”的硬性规则。

changelog.md 按现有格式追加：

```markdown
## [2026-09-22] 后端 domain/service/db/api 分层重构

### 改动标题
将后端从 API/Service 直接依赖 Repository/ORM 的结构迁移为 domain/service/db/api 四层，并保持外部契约兼容。

### 改动文件清单
新建 `domain/`、`db/models/`、`db/mappers.py`、`db/repositories/`、`api/dependencies.py`、应用服务和架构边界测试；迁移 Agent/RAG 适配器；删除旧 `models/` 和 `db/*_repo.py`。

### 关键设计决策与理由
兼容优先；domain 不依赖框架；Repository 返回领域实体且不提交事务；API 通过组合根注入 Service；AI/RAG 作为端口适配器。

### 待办
无。

### 验证结果
记录最终 pytest、py_compile、导入冒烟和接口契约测试结果。
```

- [ ] **Step 5: 运行最终验收**

Run: `uv run --cache-dir .uv-cache pytest tests -q`

Expected: `65 passed, 1 warning`。

Run: `uv run --cache-dir .uv-cache python -m compileall -q main.py api services domain db agent rag core schemas utils`

Expected: 退出码 0。

Run: `uv run --cache-dir .uv-cache python -c "from main import app; print(sorted({r.path for r in app.routes}))"`

Expected: 能打印路由集合，无 import/装配异常。

Run: `git diff --check`

Expected: 无输出。

- [ ] **Step 6: 提交**

`ash
git add -A
git commit -m "refactor(backend): 完成 domain service db api 分层"
```
















