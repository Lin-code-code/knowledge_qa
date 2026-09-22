# 后端 domain/service/db/api 分层重构设计

- 日期：2026-09-22
- 状态：已确认，已审阅
- 分支：`codex/refactor-domain-layers`
- 目标：在不改变对外 HTTP 契约、数据库表结构和配置键的前提下，将后端重构为 `api -> services -> domain`，并由 `db` 和现有 `rag/agent` 提供适配实现。

## 1. 背景

当前项目已有 `api/`、`services/`、`db/`、`models/`，但边界不完整：

- `api/chat.py` 直接创建 `ConversationRepository`，并把 ORM 实体转换为响应字段；
- `api/documents.py` 直接执行文件写入、MD5、向量写入和补偿删除；
- `services/chat_service.py` 依赖 `db.conversation_repo.ConversationRepository`；
- `services/context_builder.py`、`topic_router.py`、`summary_service.py` 等直接依赖 SQLAlchemy ORM 实体；
- `db/conversation_repo.py` 同时聚合会话、主题和长期记忆仓储，并包含 LangChain 消息转换；
- `models/` 同时被 API、Service、Repository 和测试直接引用。

现有测试基线：`43 passed, 1 warning`。

## 2. 目标与非目标

### 2.1 目标

1. 建立纯 `domain` 层：实体、枚举、领域决策对象、领域错误和能力端口。
2. 建立明确依赖方向：`api -> services -> domain`，`db -> domain`。
3. 让 API 只处理 HTTP 输入、鉴权、响应模型、状态码和依赖装配。
4. 让 Service 只编排用例和事务，不直接接触 SQLAlchemy ORM。
5. 让 Repository 和 AI/RAG 适配器实现领域端口，且 Repository 继续禁止 `commit()`。
6. 保持 `/api/*` 请求/响应、数据库表/字段、`.env` 和 YAML 配置键不变。
7. 将现有行为测试保留为重构守护测试，最后补齐分层边界测试。

### 2.2 非目标

1. 不修改数据库表结构、迁移脚本数据语义或 API 字段。
2. 不引入消息队列、事件总线、CQRS、工作单元框架或新的依赖。
3. 不重写 TopicRouter、Guard、RetrievalAgent、ReactAgent 的提示词或模型接线。
4. 不改变四层防乱说话、会话主题、长期记忆、摘要和检索的现有业务规则。
5. 不新增微服务、容器编排或分布式事务。

## 3. 目标目录结构

```text
api/
  dependencies.py          # 请求级依赖装配，唯一组合根
  chat.py                  # 会话、主题、记忆、聊天 HTTP 路由
  documents.py             # 文件 HTTP 路由
services/
  chat_service.py          # 单轮问答完整编排
  conversation_service.py  # 会话与消息用例
  topic_service.py         # 主题查询与归档用例
  memory_service.py        # 长期记忆用例、筛选和提取编排
  document_service.py      # 上传、去重、索引补偿、删除用例
  context_builder.py       # 纯应用上下文构造器
domain/
  entities.py              # 领域实体 dataclass
  enums.py                 # str 枚举
  decisions.py             # TopicDecision、TopicSegment
  errors.py                # 领域异常
  ports.py                 # Repository 与 AI/RAG 能力 Protocol
db/
  engine.py                # 异步引擎与 URL
  session.py               # 请求级事务边界
  mappers.py               # ORM <-> domain 映射
  models/                  # SQLAlchemy ORM
    __init__.py
    base.py
    conversation.py
    memory_item.py
    uploaded_file.py
  repositories/
    __init__.py
    conversation.py
    topic.py
    memory.py
    file.py
agent/
  react_agent.py
  retrieval_agent.py
  rewrite_agent.py
  topic_router.py          # 从 services 迁移的 LLM 适配器
  summary_agent.py         # 从 services 迁移的 LLM 适配器
  guard_agent.py           # 从 services 迁移的 LLM 适配器
  memory_agent.py          # 长期偏好提取适配器
rag/
  ...                      # 检索、向量库、模型工厂保持不变
schemas/
  ...                      # HTTP DTO，保持 Pydantic
```

`models/`、旧 `db/*_repo.py` 和旧 Service 路径在迁移期间可有临时转发；最终业务代码只使用上述新路径。

## 4. 依赖规则

允许：

```text
api        -> services, schemas, core, domain
services   -> domain, core, utils
db         -> domain, core, db.models, db.mappers
agent/rag  -> domain, core, utils
api/dependencies -> services, db, agent, rag, core
```

禁止：

```text
domain     -> fastapi, sqlalchemy, langchain, db, services, api, agent, rag
services   -> fastapi, sqlalchemy, db, api, agent, rag
db         -> services, api, agent, rag
api        -> db.repositories, db.models, ORM session 细节
```

`api/dependencies.py` 是唯一组合根，可以同时导入 Service、Repository 实现和 AI 适配器。Service 构造函数只接收 Protocol 或纯应用组件。

## 5. 领域模型

所有领域实体使用 `dataclass(slots=True)`，时间字段使用 `datetime`，ID 使用 `UUID` 或 `int`，字段与数据库保持一一对应。

### 5.1 实体

- `Conversation`：`id`、`user_id`、`title`、`created_at`、`updated_at`
- `Message`：`id`、`conversation_id`、`topic_id`、`turn_id`、`role`、`content`、`intent`、`scope_label`、`is_refusal`、`memory_eligible`、`created_at`
- `ConversationTopic`：`id`、`conversation_id`、`topic_label`、`summary`、`last_intent`、`scope_label`、`confidence`、`status`、`summary_version`、`created_at`、`updated_at`
- `MemoryItem`：`id`、`user_id`、`memory_type`、`memory_key`、`content`、`source_message_id`、`confidence`、`expires_at`、`status`、`created_at`、`updated_at`
- `UploadedFile`：`id`、`filename`、`md5_hex`、`size`、`uploaded_at`
- `FileSummary`：`id`、`filename`、`size`、`chunks`（文件列表读模型）

### 5.2 枚举

- `Role`：`human`、`ai`、`system`
- `ScopeLabel`：`IN`、`OUT`
- `TopicAction`：`CONTINUE`、`NEW_TOPIC`、`MIXED`、`CLARIFY`、`OUT_OF_SCOPE`
- `TopicStatus`：`active`、`archived`

枚举继承 `str, Enum`，序列化和数据库写入值保持现有字符串。`ChatAnswer` 与 `MemoryCandidate` 是端口传输用的 `dataclass(slots=True)`：前者包含 `answer`、`sources`，后者包含提取出的偏好字段。

### 5.3 领域错误

- `ConversationNotFoundError`
- `TopicNotFoundError`
- `MemoryNotFoundError`
- `DocumentNotFoundError`
- `DuplicateDocumentError`
- `EmptyDocumentError`
- `UnsupportedDocumentTypeError`
- `DocumentIndexError`

Service 不抛 `HTTPException`。API 负责将领域错误映射为现有状态码与 `detail` 文案。

## 6. 端口设计

### 6.1 Repository 端口

- `ConversationRepositoryPort`
  - `create(user_id, title) -> Conversation`
  - `get(conversation_id) -> Conversation | None`
  - `list_by_user(user_id, limit, offset) -> list[Conversation]`
  - `delete(conversation_id) -> bool`
  - `get_messages(conversation_id, limit) -> list[Message]`
  - `get_recent_topic_messages(topic_id, max_turns, max_tokens) -> list[Message]`
  - `add_turn(...) -> tuple[Message, Message]`
- `TopicRepositoryPort`
  - `get_active(conversation_id) -> ConversationTopic | None`
  - `create(conversation_id, label, intent, scope, confidence) -> ConversationTopic`
  - `switch(...) -> ConversationTopic`
  - `get(conversation_id, topic_id) -> ConversationTopic | None`
  - `list(conversation_id) -> list[ConversationTopic]`
  - `archive(topic_id) -> bool`
  - `update_metadata(...) -> None`
  - `update_summary(topic_id, summary, expected_version) -> bool`
- `MemoryRepositoryPort`
  - `list_active(user_id, limit) -> list[MemoryItem]`
  - `upsert(...) -> MemoryItem`
  - `delete_one(user_id, memory_id) -> bool`
  - `delete_all(user_id) -> int`
- `FileRepositoryPort`
  - `get_by_md5(md5_hex) -> UploadedFile | None`
  - `save(...) -> UploadedFile`
  - `list_all() -> list[FileSummary]`
  - `delete_by_id(file_id) -> bool`
  - `delete_index_records(file_id) -> int`

### 6.2 AI/RAG 能力端口

- `ChatAgentPort.execute(query, context, topic_label) -> ChatAnswer`
- `TopicClassifierPort.route(message, topic, recent_messages, memories) -> TopicDecision`
- `GuardPort.check_question_scope(query) -> bool`
- `GuardPort.check(query, answer) -> tuple[bool, str]`
- `GuardPort.refusal_text -> str`
- `SummaryGeneratorPort.summarize(topic, query, answer) -> str`
- `MemoryExtractorPort.extract(user_message) -> list[MemoryCandidate]`
- `DocumentIndexPort.load_document(file_id, target_path) -> list[str] | None`
- `DocumentIndexPort.delete_documents(ids) -> None
- `AsyncDocumentReader`：`async read(size: int) -> bytes`，由 API 层的 `UploadFile` 满足

生产实现继续复用现有 `agent/`、`rag/` 模型、提示词和单例逻辑；只调整适配接口与位置，不改变模型调用顺序。

## 7. Service 用例

### 7.1 ChatService

`ChatService.process_message(message, chat_id, user_id) -> ChatResult` 保持现有业务流程：

1. 检查会话存在；
2. 读取 active topic、最近有效轮次和长期偏好；
3. 主题路由；
4. CLARIFY / OUT_OF_SCOPE / MIXED 分支；
5. L0 域内预检；
6. 准备或切换主题；
7. 构建受限上下文；
8. 执行 ReactAgent；
9. L3 输出检查；
10. 写入 Human/AI 配对消息；
11. 更新摘要；
12. 提取并保存长期偏好。

`ChatResult` 保留在应用层，不作为 HTTP DTO。Service 不再创建 `ConversationRepository`，所有依赖由构造函数注入。

### 7.2 ConversationService

负责创建会话、列出会话、读取消息、删除会话。创建会话时由 Service 依次调用会话 Repository 和 Topic Repository；是否创建默认主题由 `conversation_memory_enabled` 决定。

### 7.3 TopicService

负责主题列表、详情和归档。所有“会话不存在/主题不存在”判断返回领域错误或结果，由 API 映射 404。

### 7.4 MemoryService

保留 `list_for_prompt`、`select_for_query`、`extract_and_save`，并新增/承接列表和删除用例。它依赖 `MemoryRepositoryPort` 与 `MemoryExtractorPort`，继续保证 `anonymous` 不写入、过期偏好不注入。

### 7.5 DocumentService

接收文件名和异步读取接口，不导入 FastAPI：

1. 校验扩展名；
2. 流式写临时文件并计算 MD5/大小；
3. 空文件检查与重复检查；
4. 调用 `DocumentIndexPort` 写向量；
5. 调用 `FileRepositoryPort` 保存元数据；
6. 元数据保存失败时补偿删除向量；
7. 始终清理临时文件；
8. 提供文件列表和删除用例。

### 7.6 ContextBuilder

保留纯应用组件定位，输入改为领域实体，不再导入 `models`。过滤、Token 预算、摘要/最近轮次/长期偏好优先级保持现有行为。

## 8. db 适配层

- SQLAlchemy ORM 移到 `db/models/`。
- `db/mappers.py` 提供函数完成 ORM 与领域实体转换。
- `db/repositories/` 中每个实现构造函数接收同一个 `AsyncSession`。
- Repository 不调用 `commit()`；允许 `flush()`、`refresh()`、`execute()`。
- `get_db()` 保持请求结束统一提交、异常回滚。
- `ConversationRepository` 不再组合 Topic/Memory 子仓储；由组合根分别创建。
- `db.file` 实现仍可在同一会话中删除 `langchain_pg_embedding`，以保留当前删除语义和事务一致性。
- 文件列表与向量表 JOIN 的 SQL 保持不变。

## 9. API 与组合根

`api/dependencies.py` 提供至少以下 FastAPI 依赖：

- `get_conversation_service`
- `get_topic_service`
- `get_memory_service`
- `get_chat_service`
- `get_document_service`

依赖内部使用 `Depends(get_db)` 获取同一请求的 Session，创建 Repository 实现和适配器，再注入 Service。路由只做：

1. 解析路径/请求字段；
2. 调用 Service；
3. 将应用结果映射到现有 Pydantic 响应；
4. 将领域错误映射到既有 HTTP 状态码和 `detail`。

`api/` 最终不得出现 `sqlalchemy`、`db.repositories`、`db.models` 或直接 Repository 实例化。

## 10. 错误与兼容语义

保留以下现有返回语义：

- 空消息：`400`，`消息不能为空`
- 非法 chatId/conversation_id/topic_id/memory_id：`400`，`<字段> 格式无效`
- 会话不存在：`404`，`对话不存在`
- 主题不存在：`404`，`主题不存在`
- 长期记忆不存在：`404`，`长期记忆不存在`
- 重复文件：`400`，`文件已存在于向量库中！`
- 类型不支持、空文件：`400`，保持现有文案
- 未处理异常：全局 `500` 通用文案

响应模型字段保持：`answer`、`sources`、`chatId`、`topicId`、`topicAction` 以及主题/记忆响应字段不变。

## 11. 测试与验收

### 11.1 守护测试

- 保留并迁移现有 43 个测试。
- 每个迁移步骤后运行 `uv run --cache-dir .uv-cache pytest tests -q`。
- 对改动 Python 文件运行 `uv run --cache-dir .uv-cache python -m py_compile <files>`。
- 运行 `from main import app` 导入冒烟，检查路由和依赖装配。

### 11.2 新增测试

- 领域层源码静态检查：禁止导入 FastAPI、SQLAlchemy、LangChain、api、db、services、agent、rag。
- Mapper 测试：字段、枚举、时间、UUID 双向转换。
- Repository 测试优先使用 SQL 编译或轻量 fake；不要求真实 PostgreSQL。
- Service 测试使用 fake ports，继续覆盖主题动作、记忆过滤、拒答、混合问题和摘要失败降级。
- API 测试验证领域异常到 HTTP 状态码的映射。

### 11.3 验收标准

1. `domain` 不含外部框架依赖。
2. `services` 不导入 `db`、`api`、FastAPI、SQLAlchemy。
3. `api` 不直接创建 Repository，不访问 ORM 字段。
4. Repository 无 `commit()`。
5. 现有 HTTP、数据库和配置兼容。
6. 所有 pytest 测试通过。
7. README、AGENTS.md、changelog.md 与新目录和依赖规则同步。

## 12. 迁移阶段

1. **领域与适配层**：新增 `domain/`、`db/models/`、`db/mappers.py`、`db/repositories/`，并保留迁移期转发。
2. **Service 迁移**：将 ContextBuilder、TopicRouter、Summary、Memory、Chat 改为领域对象和端口注入。
3. **API 迁移**：新增 `api/dependencies.py`，路由改调 Service，移除 Repository/DTO 拼装。
4. **文档与清理**：移除兼容转发和旧 `models/`，更新 README、AGENTS、changelog。
5. **验证与提交**：跑全部测试、py_compile、导入冒烟，每个逻辑阶段测试通过后提交。

## 13. 风险与缓解

- **一次性大改导致回归**：按领域、仓储、Service、API 顺序迁移，每步跑测试。
- **ORM 与领域字段漂移**：Mapper 测试覆盖全部字段。
- **跨事务文件上传语义变化**：DocumentService 保留补偿删除和临时文件清理。
- **LangChain 对象泄漏到领域层**：领域端口只使用 dataclass、普通类型和 Protocol。
- **过度抽象**：只定义实际有生产实现和测试替身的端口，不引入 UnitOfWork、事件总线或领域工厂。
- **API 兼容回归**：保留现有错误文案和响应字段测试。

## 14. 已确认决策

- 采用兼容优先的渐进式重构。
- `domain` 不依赖 FastAPI、SQLAlchemy 和 LangChain。
- 外部 HTTP、数据库表结构和配置键不变。
- Repository 继续禁止提交事务。
- AI/RAG 能力保留现有实现，通过端口注入到 Service。

