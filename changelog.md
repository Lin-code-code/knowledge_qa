# Changelog（AI 进度日志）

> 本文件用于跨会话传递项目进度，解决 AI 上下文超限问题。
> 每完成一个大功能，由当次会话 AI 总结"做了什么改动"并追加一条记录。
> 开新会话时对 AI 说："请先阅读 changelog.md 了解当前进度。"

## 记录格式
每条记录包含：
- 日期
- 功能/改动标题
- 改动文件清单（新建 / 修改）
- 关键设计决策与理由
- 遗留事项 / 待办
- 验证方式与结果

---

## [2026-09-22] 后端分层重构 Task 6：会话、主题、记忆应用服务与 ContextBuilder

### 改动标题
新建 `ConversationService`、`TopicService`；把 `MemoryService` 重写为消费 `MemoryRepositoryPort`/`MemoryExtractorPort` 的应用服务；`ContextBuilder` 改为只依赖领域实体与枚举。四个 `services` 文件不再导入 ORM、`db`、`api` 或 `agent`。

### 改动文件清单
新建：
- `services/conversation_service.py` — `ConversationService`（创建会话时可选建默认主题）
- `services/topic_service.py` — `TopicService`（缺主题抛 `TopicNotFoundError`，缺会话抛 `ConversationNotFoundError`）
- `tests/test_app_services.py` — 三个应用服务契约失败测试（简报内容，逐字）

重写：
- `services/memory_service.py` — 构造函数 `(repository, extractor=None)`；模型调用改为通过 `MemoryExtractorPort` 消费；保留 `_ALLOWED_KEYS`/`_INTENT_KEYWORDS`/`_SHOPPING_KEYWORDS`/`_SHOPPING_INTENTS`/`_is_explicit` 与 `select_for_query` 全部筛选规则

修改：
- `services/context_builder.py` — ORM 导入改 `domain.entities`，`scope_label == "OUT"` 改 `ScopeLabel.OUT`，算法逐行未动
- `tests/test_context_builder.py` — 改用领域 dataclass 构造主题/消息/记忆（断言原文未动）
- `tests/test_memory_service.py` — 改用领域 `MemoryItem` 并注入 fake `MemoryExtractorPort`（场景与断言保留）
- `changelog.md` — 追加本次进度记录

未修改 `services/chat_service.py`（Task 7 切换）、`tests/test_chat_service_memory.py`，也未改 `domain/`、`db/`、`models/`、`agent/`（已验证产物）。

无需更新 `README.md`：外部 HTTP 契约、表结构、配置键与依赖均未变化。

### 关键设计决策与理由
1. **保持 Task 7 前的调用兼容**：`MemoryService` 构造仍接受单个位置参数（`MemoryService(self.store.memories)`），`select_for_query` 仍是实例方法且签名为 `(memories, query, intent=None)`；`extractor is None` 时 `extract_and_save` 静默返回，故无需改 `chat_service.py`，也无需弱化 `test_chat_service_memory.py` 的断言。
2. **模型抽取下沉到端口**：记忆提取的 prompt 与模型调用已由 Task 5 的 `agent/memory_agent.py` 承担，本任务只通过 `MemoryExtractorPort` 消费；服务层策略（允许类别、置信度阈值、显式表达正则）仍留在 `MemoryService`。
3. **方法顺序调整（与简报唯一的实现差异）**：简报中 `ConversationService` 把 `list` 写在 `get_messages` 之前，类体内 `list` 会遮蔽内置 `list`，使其后的 `list[Message]` 注解在 Python 3.13 抛 `TypeError: 'function' object is not subscriptable`；故把 `list` 方法移到使用 `list[...]` 注解的方法之后，公开签名与行为不变。
4. **`context_builder.py` 只做机械替换**：上下文隔离规则（仅 `topic_id` 严格匹配、`memory_eligible`、非拒答、非 OUT）逐行保留；`str Enum` 与字符串比较成立，`item.role == "human"` 与 `{"human","ai"} <= roles` 无需改写。
5. **`_is_explicit` 颜色正则写法**：原转义形式的 Unicode 区间改以等价字面区间 `[一-鿿]` 书写（同一 U+4E00–U+9FFF 范围），规避转义歧义，且经比对用例逐例验证一致。

### 遗留事项 / 待办
- `MemoryService` 在 `chat_service.py` 中仍以 `extractor=None` 构造，长期记忆抽取要等 Task 7 注入真实 `get_memory_extractor()` 才生效。
- `TopicService.list` 依赖 `TopicRepositoryPort.list`（Task 4 已实现），其成功分支当前无测试覆盖。

### 验证方式与结果
- TDD RED：`uv run --cache-dir .uv-cache pytest tests/test_app_services.py -q`，`ModuleNotFoundError: No module named 'services.conversation_service'`，`1 error in 0.12s`。
- TDD GREEN（聚焦）：`uv run --cache-dir .uv-cache pytest tests/test_app_services.py tests/test_context_builder.py tests/test_memory_service.py -q`，`13 passed in 0.07s`。
- 衔接回归（未修改的测试）：`uv run --cache-dir .uv-cache pytest tests/test_chat_service_memory.py -q`，`12 passed, 1 warning in 0.66s`。
- 全量回归：`uv run --cache-dir .uv-cache pytest tests -q`，`59 passed, 1 warning in 0.99s`（警告仍是既有 `langgraph` 待弃用提示）。
- 边界自证：AST 扫描新建/改写的四个 `services` 文件，导入集合与 `{db, api, fastapi, sqlalchemy, rag, agent}` 无交集，输出 `boundary self-check passed`。
- 正则保真：`_is_explicit` 颜色正则与 HEAD 版本对同一组用例逐例结果一致，输出 `color regex equivalence OK`。

---

## [2026-09-22] 后端分层重构 Task 5：AI/RAG 适配器迁移到端口

### 改动标题
把主题路由、滚动摘要、L0/L3 护栏、长期记忆提取和聊天执行迁移到 `agent/`，实现 `domain/ports.py` 的五个 AI 能力 Protocol；旧 `services/*` 改为薄转发 shim，保证 Task 7 之前 `services/chat_service.py` 与既有测试不断裂。

### 改动文件清单
迁移（`git mv`，git 识别为重命名）：
- `services/topic_router.py` → `agent/topic_router.py`（`TopicRouter`，改用领域实体/决策/枚举）
- `services/summary_service.py` → `agent/summary_agent.py`（`SummaryService` → `SummaryAgent`）
- `services/guard_service.py` → `agent/guard_agent.py`（`GuardService` → `GuardAgent`，含工厂改名）

新建：
- `agent/memory_agent.py` — `MemoryExtractor` + `get_memory_extractor()`（从 `services/memory_service.py` 抽离记忆提取）
- `agent/chat_agent.py` — `ChatAgent` + `get_chat_agent()`，`execute()` 返回 `ChatAnswer`
- `tests/test_ai_adapters.py` — 适配器契约失败测试（简报内容，逐字）
- `services/topic_router.py`、`services/summary_service.py`、`services/guard_service.py` — 兼容转发 shim

修改：
- `rag/rag_service.py` — 新增 `reset_sources_collection(token)`（只重置 `_sources_ctx`，与 `start_sources_collection` 的 token 语义配套）
- `tests/test_topic_router.py` — 导入改为 `agent.topic_router` + `domain.entities`；构造器改为领域 dataclass（断言原文未动）
- `tests/test_chat_service_memory.py` — 仅把 `schemas.topic` 的 `TopicDecision/TopicSegment` 引用改为 `domain.decisions`
- `changelog.md` — 追加本次进度记录

未修改 `domain/`、`db/`、`models/`、`services/memory_service.py`（Task 6 重写）、`services/chat_service.py`（Task 7 切换）。

无需更新 `README.md`：外部 HTTP 契约、数据库表结构、`.env` 与 YAML 配置键、依赖均未变化。

### 关键设计决策与理由
1. **`_parse` 用枚举承载分支判定**：`TopicAction`/`ScopeLabel` 是 `str Enum`，`TopicDecision` 改为 dataclass 后仍与字符串比较成立；`OUT/OUT_SCOPE/OUT-OF-SCOPE` 别名归一化与"scope=OUT 强制 OUT_OF_SCOPE"语义原样保留。
2. **`_fallback` 返回 `TopicDecision` dataclass**：使用 `TopicAction.CONTINUE`/`TopicAction.CLARIFY` 与 `ScopeLabel.IN`，四段文案与澄清问题一字未改。
3. **ChatAgent 用 `try/finally` 复位两组 token**：`reset_sources_collection(source_token)` + `reset_topic_context(topic_token)`，异常路径也复位，避免 contextvar 泄漏到同一 Task 的后续请求；成功路径 `ChatAnswer(answer=..., sources=list(collect_sources()))`。
4. **shim 双名导出**：guard shim 同时导出旧名 `GuardService`/`get_guard_service` 与新名 `GuardAgent`/`get_guard_agent`，Task 7 前后两套调用方都能用；topic/summary shim 按简报只导出旧名。
5. **`agent/` 不反向依赖**：五个适配器只依赖 `domain`/`rag`/`utils`/`core`，无 `services`/`api` 导入（脚本校验通过）。
6. **不动 `services/chat_service.py`**：当前 `_execute_agent` 仍直接使用 `rag.rag_service` 的四个 helper 并自行 `_sources_ctx.reset`，与新增的 `reset_sources_collection` 并存、互不影响。

### 遗留事项 / 待办
- 三个 `services/*` shim 仅为兼容转发，Task 7 切换调用方后由 Task 9 删除。
- `DocumentIndexPort` 未在本任务实现：Task 5 的五个适配器不含文档索引，该端口由 Task 8 的 `DocumentService` 消费（注入式实现）。

### 验证方式与结果
- TDD RED：`uv run --cache-dir .uv-cache pytest tests/test_ai_adapters.py -q`，`ModuleNotFoundError: No module named 'agent.summary_agent'`，`1 error in 0.13s`。
- TDD GREEN（聚焦）：`uv run --cache-dir .uv-cache pytest tests/test_ai_adapters.py tests/test_topic_router.py -q`，`9 passed in 0.22s`。
- 全量回归：`uv run --cache-dir .uv-cache pytest tests -q`，`56 passed, 1 warning in 1.08s`（警告仍是既有 `langgraph` 待弃用提示）。
- 签名自证：`inspect.signature` 逐参数比对五个适配器与 `ChatAgentPort`/`TopicClassifierPort`/`GuardPort`/`SummaryGeneratorPort`/`MemoryExtractorPort` 的名称/顺序/默认值，全部一致；`ChatAgent.execute` 为协程，其余四个保持同步，输出 `SIGNATURES_OK`。
- 边界自证：`agent/*.py` 的 AST 导入集合与 `{services, api}` 无交集，输出 `NO_FORBIDDEN_IMPORTS_OK`。
- 护栏保真：`HEAD:services/guard_service.py` 归一化换行并替换 `GuardService`→`GuardAgent` 后与 `agent/guard_agent.py` 逐行比对，唯一差异是工厂函数名 `get_guard_service`→`get_guard_agent`，解析正则/L0/L3 提示词/默认放行/`refusal_text` 语义不变。
- token 语义自证：`reset_sources_collection(token)` 复位后 `_sources_ctx.get() is None`；`ChatAgent.execute` 成功与异常两条路径都使 `_sources_ctx`/`_topic_label_ctx` 复位，输出 `RESET_SOURCES_OK` / `CHAT_AGENT_TOKENS_OK`。

---

## [2026-09-22] 后端分层重构 Task 4：拆分并实现领域仓储端口

### 改动标题
新增 `db/repositories/` 包，把旧 `db/*_repo.py` 的查询逻辑按领域端口拆成四个 SQLAlchemy 仓储实现，公开出入口一律返回领域实体或朴素值，不再泄漏 ORM 行对象。

### 改动文件清单
新建：
- `db/repositories/__init__.py` — 统一导出四个实现类
- `db/repositories/conversation.py` — `SqlAlchemyConversationRepository`（会话 + 消息 + 最近主题轮次）
- `db/repositories/topic.py` — `SqlAlchemyTopicRepository`（含乐观锁 `update_summary`）
- `db/repositories/memory.py` — `SqlAlchemyMemoryRepository`
- `db/repositories/file.py` — `SqlAlchemyFileRepository`
- `tests/test_repository_contracts.py` — 方法存在性与"仓储禁止 commit"契约测试

修改：
- `changelog.md` — 追加本次进度记录

未修改 `db/conversation_repo.py` 等旧仓储（按计划由 Task 9 统一删除），也未修改 `db/models/`、`db/mappers.py`、`domain/`（已验证产物）。

无需更新 `README.md`：本次只在内部新增适配器层，外部 HTTP、数据库表结构、`.env` 与 YAML 配置键、依赖均未变化。

### 关键设计决策与理由
1. **旧条件原样迁移**：`get_recent_topic_messages` 逐行保留旧 `get_recent_topic_records` 的过滤条件（`memory_eligible` 为真、非拒答、`scope_label != 'OUT'`、`turn_id` 非空）、`created_at desc, id desc` 排序、`.limit(max_turns * 4)`、按 `turn_id` 分组、只保留同时含 human/ai 的轮次、按时间排序与 Token 预算，唯一差异是查询对象换成 `MessageModel`、返回前走 `to_message`。
2. **`list_all` 的跨表 UUID 关联原样保留**：`REPLACE(uf.id::TEXT, '-', '') = (lpe.cmetadata ->> 'file_id')` 文本逐字未改，只把返回从 `dict` 换成 `to_file_summary(mapping)`。
3. **端口命名对齐**：旧 `switch_topic` 改名 `switch`、`delete_vector_embeddings` 改名 `delete_index_records`、`delete_by_id` 参数改 `UUID`，与 Task 2 的 Protocol 严格一致；已用脚本逐参数校验四个实现的签名（参数名 + 默认值）与对应 Protocol 完全相同。
4. **枚举落库显式取值**：`scope_label` 写库时统一用 `scope_label.value`，落盘字符串与旧路径（调用方传 `"IN"`/`"OUT"` 字符串）完全一致。
5. **单会话注入**：四个实现都只接收一个 `AsyncSession`，由未来的组合根 `api/dependencies.py` 统一创建；会话仓储不再组合 Topic/Memory 子仓储。

### 遗留事项 / 待办
- 旧 `db/*_repo.py` 仍被 `services/` 与 `api/` 引用，Task 5-7 完成切换后由 Task 9 删除。
- 仓储目前只有契约测试，未接入真实 PostgreSQL 的集成测试（设计规格允许优先用 SQL 编译/轻量 fake）。

### 验证方式与结果
- TDD RED：`uv run --cache-dir .uv-cache pytest tests/test_repository_contracts.py -q`，确认 `ModuleNotFoundError: No module named 'db.repositories'`。
- TDD GREEN：`uv run --cache-dir .uv-cache pytest tests/test_repository_contracts.py -q`，`2 passed in 0.30s`。
- 全量回归：`uv run --cache-dir .uv-cache pytest tests -q`，`52 passed, 1 warning in 1.05s`（警告仍是既有 `langgraph` 待弃用提示）。
- 边界自检：`db/repositories/` 无 `services`/`api`/`agent`/`rag` 导入，无 `.commit(`；`_estimate_tokens` 与旧实现同值（`"你好world"` → 2）；`list_all` 与删除向量两条原始 SQL 文本与旧实现逐字相同。

---

## [2026-09-22] 后端分层重构 Task 3：迁移 ORM 并建立领域映射器

### 改动标题
把 `models/` 迁移到 `db/models/`，新增 `db/mappers.py` 承担 ORM 行对象到领域实体的转换，并保留 `models/` 兼容转发包，保证 Task 7 之前旧导入路径不断裂。

### 改动文件清单
移动：
- `models/__init__.py`、`base.py`、`conversation.py`、`memory_item.py`、`uploaded_file.py` → `db/models/`（`git mv`，保留历史）

新建：
- `db/mappers.py` — `to_conversation`、`to_message`、`to_topic`、`to_memory_item`、`to_uploaded_file`、`to_file_summary`、`to_scope_label`
- `models/__init__.py`、`models/base.py`、`models/conversation.py`、`models/memory_item.py`、`models/uploaded_file.py` — 临时兼容转发包（Task 9 删除）
- `tests/test_mappers.py` — 会话字段保真、消息/主题枚举转换测试

修改：
- `db/models/__init__.py` — 改为按 `db.models.*` 绝对导入并导出 ORM 类
- `db/models/conversation.py`、`memory_item.py`、`uploaded_file.py` — `from models.base import Base` 改为 `from db.models.base import Base`
- `changelog.md` — 追加本次进度记录

无需更新 `README.md`：外层导入路径与旧数据表、接口、配置均未变化，`services/`、`db/*_repo.py` 仍通过兼容包按原样导入。

### 关键设计决策与理由
1. `db/mappers.py` 是唯一把 ORM 行对象翻成领域实体的地方，后续 Repository 只调用 mapper，不再各自拼装领域对象。
2. `to_scope_label` 对 `None` 返回 `None`、其余非 `OUT` 一律归一为 `IN`，兼容旧数据里 `scope_label` 为空或异常值的行。
3. 兼容包只做同名转发（`models.conversation.Conversation is db.models.conversation.Conversation`），不是复制类，避免出现两套 ORM 元数据；Task 9 统一删除。

### 遗留事项 / 待办
- `services/*`、`db/*_repo.py`、部分测试仍在导入 `models.*`，由 Task 4-7 逐步切到 `db.models` / 领域实体，Task 9 删除兼容层。

### 验证方式与结果
- TDD RED：`uv run --cache-dir .uv-cache pytest tests/test_mappers.py -q`，确认 `ModuleNotFoundError: No module named 'db.mappers'`。
- TDD GREEN：`uv run --cache-dir .uv-cache pytest tests/test_mappers.py -q`，`2 passed in 0.29s`。
- 兼容性冒烟：`models.conversation.Conversation is db.models.conversation.Conversation` 为 `True`；`db.mappers` 七个 `to_*` 函数齐全。
- 全量回归：`uv run --cache-dir .uv-cache pytest tests -q`，`50 passed, 1 warning in 1.03s`；警告来自既有 `langgraph` 依赖的待弃用提示。

---

## [2026-09-22] 后端分层重构 Task 2：定义仓储与 AI/RAG 应用端口

### 改动标题
新增零框架依赖的 `domain.ports` 协议层，为后续数据库适配器、Agent/RAG 适配器和应用服务提供稳定契约。

### 改动文件清单
新建：
- `domain/ports.py` — 会话、主题、记忆、文件仓储端口，以及聊天、主题分类、Guard、摘要、记忆提取、文档索引和异步文档读取端口
- `tests/test_domain_ports.py` — 校验聊天 Agent 参数和会话写入参数的契约测试

修改：
- `changelog.md` — 追加本次进度记录

无需更新 `README.md`：本次仅建立内部 Protocol 契约，没有改变外部 HTTP、数据库、配置或依赖行为。

### 关键设计决策与理由
1. 所有端口仅依赖标准库和 `domain` 内实体/决策/枚举，延续领域层零框架依赖边界。
2. 仓储与聊天执行端口声明为异步接口，同步的领域决策、分类、Guard、摘要、记忆提取和文档索引能力保持同步签名。
3. 端口签名严格对齐现有调用需求，不提前扩展 Task 2 以外的能力。

### 遗留事项 / 待办
- 后续任务基于这些端口实现基础设施适配器和应用服务编排。

### 验证方式与结果
- TDD RED：`uv run --cache-dir .uv-cache pytest tests/test_domain_ports.py -q`，确认 `ModuleNotFoundError: No module named 'domain.ports'`。
- TDD GREEN：`uv run --cache-dir .uv-cache pytest tests/test_domain_layer.py tests/test_domain_ports.py -q`，`5 passed in 0.03s`。
- 编译检查：`uv run --cache-dir .uv-cache python -m py_compile domain/ports.py tests/test_domain_ports.py`，退出码 0。
- 全量回归：`uv run --cache-dir .uv-cache pytest tests -q`，`48 passed, 1 warning in 1.22s`；警告来自既有 `langgraph` 依赖的待弃用提示。

---

## [2026-09-22] 后端分层重构 Task 1：建立纯领域实体、枚举、错误与决策对象

### 改动标题
新增零框架依赖的 `domain` 基础层，为后续数据库映射、仓储端口和应用服务提供稳定的领域契约。

### 改动文件清单
新建：
- `domain/__init__.py` — 导出领域实体与枚举
- `domain/enums.py` — `Role`、`ScopeLabel`、`TopicAction`、`TopicStatus`
- `domain/entities.py` — `Conversation`、`Message`、`ConversationTopic`、`MemoryItem`、`UploadedFile`、`FileSummary`
- `domain/decisions.py` — `TopicDecision`、`TopicSegment`、`ChatAnswer`、`MemoryCandidate`
- `domain/errors.py` — 会话、主题、记忆和文档领域异常
- `tests/test_domain_layer.py` — 依赖边界、枚举/默认值和 slots dataclass 测试

修改：
- `changelog.md` — 追加本次进度记录

无需更新 `README.md`：本次仅建立内部领域契约，没有改变外部 HTTP、数据库或配置行为。

### 关键设计决策与理由
1. 领域层只依赖标准库和 `domain` 内部模块，避免 FastAPI、SQLAlchemy、LangChain 及上层业务包反向侵入。
2. 实体和决策对象统一使用 `dataclass(slots=True)`，保证后续映射边界轻量且行为稳定。
3. 异常按语义分别继承 `LookupError`、`ValueError`、`RuntimeError`，供后续服务层映射使用。

### 遗留事项 / 待办
- 后续 Task 2+ 按既定端口和映射任务消费这些领域对象。

### 验证方式与结果
- TDD RED：`uv run --cache-dir .uv-cache pytest tests/test_domain_layer.py -q`，预期 `ModuleNotFoundError: No module named 'domain'`，已确认。
- TDD GREEN：同一聚焦命令通过，`3 passed in 0.02s`。
- 编译检查：对 6 个新增 Python 文件运行 `uv run --cache-dir .uv-cache python -m py_compile ...`，退出码 0。
- 全量回归：`uv run --cache-dir .uv-cache pytest tests -q`，`46 passed, 1 warning in 1.58s`；警告来自既有 `langgraph` 依赖的待弃用提示。
- 提交：`2ed4d93 refactor(domain): 建立纯领域实体与决策对象`。

---
## [2026-08-23] 企业级会话记忆升级：真实环境全量验证（迁移/接口/端到端/浏览器）

### 改动标题
在真实 PostgreSQL + 真实模型（DeepSeek/SiliconFlow/Ollama）环境下完成"企业级会话记忆升级"的全部验证任务：数据库迁移、服务启动、鉴权冒烟、会话记忆端到端 7 场景、主题与记忆接口、浏览器级验收，并记录发现的问题。

### 改动文件清单
本次仅修改：
- `changelog.md` — 追加本条验证记录
- `backups/conversations_messages_20260823_111815.dump` — 迁移前备份（pg_dump，7.4KB）
- 临时验证脚本（`scripts/_*.ps1/_*.py/_*.sql`）已全部清理；`scripts/migrate_conversation_memory.sql` 未改动

无需更新 `README.md`：本次验证未改变任何外部可见行为，README 描述（接口字段、主题路由行为表、鉴权、迁移说明）与实测一致。

### 验证结果（真实环境，全部实测）

**前置检查**：`192.168.245.120:5432` TCP 连通（TcpTestSucceeded=True）；`.env` 含 HOST/PORT/USER/PASSWORD/DBNAME；Ollama 运行中（11 个模型，含 qwen3.5:4b）；`DEEPSEEK_API_KEY`/`SILICONFLOW_API_KEY` 已设置；`API_KEYS` 未配置（步骤3测试后已恢复）。

**步骤1 迁移**：备份文件存在（迁移前 11:18 创建）；`conversation_topics`/`memory_items` 表存在；`messages` 6 个新列齐全；每会话恰好 1 个 active 主题（0 坏记录）；旧消息 topic_id 全部归入默认主题、turn_id 全部非空；当前库无含"暂无法回答该问题"旧消息（拒答标记 0=0 一致）；再次执行迁移脚本全部"已存在，跳过"，EXIT_CODE=0（幂等性通过）。

**步骤2 服务**：`http://127.0.0.1:8000` 运行中；`/`、`/docs`、`/openapi.json` 200；OpenAPI 含 `/api/chat/{conversation_id}/topics`、`/topics/{topic_id}`、`/topics/{topic_id}/archive`、`/api/memory`、`/api/memory/{memory_id}`。

**步骤3 鉴权冒烟**：未配置 `API_KEYS` 时 `/api/conversations` 正常返回（DB 连通）；临时配置 `dev-key-1` 后无 key 401、错误 key 401、正确 key 200（已恢复配置）；multipart 伪造 `<img src=x onerror=alert(1)>.txt` 上传成功，前端纯文本显示不执行脚本；测试文件已删除，知识库恢复 3 个正式文件。

**步骤4 端到端（真实模型）**：数据库证据——场景1 建会话 e155ac29（主题"纯棉T恤护理"，summary_version=2）；场景2 同一 chatId CONTINUE 不新建主题；场景3 股票问题后新会话"服装咨询"主题（不补答股票）；场景4 写入 `memory_items size=L confidence=0.95`（尺码推荐主题 summary_version=3）；场景5 羽绒服单主题；场景7 降级日志确认——`TopicRouter 路由失败，进入受限降级`（11:43:19）、`SummaryService 摘要更新失败，保留旧摘要`（11:39:59），降级后回答仍返回。

**步骤5 主题/记忆接口**：列表接口字段为 topic_id/topic_label/last_intent/scope_label/confidence/status/created_at/updated_at（不含 summary）；详情接口含 summary（677 字符）；归档后 status=archived 且列表正确；memory 接口——anonymous GET 空、anonymous DELETE 不影响真实用户、真实用户列出/删除单条/404 语义/清空全部均正确，其他用户不受影响。

**步骤6 浏览器验收（Chrome headless + CDP）**：恶意文件名在文件列表纯文本显示（img 标签数 0、无 img HTML、无 alert 弹窗）；多轮对话后顶部显示当前主题标签；CLARIFY 显示"需要澄清"提示；主题历史弹窗显示主题列表 + 进行中/已归档徽章、不含摘要；澄清问题在消息区展示；同会话追问 CONTINUE 复用 chatId/topicId（CDP 抓取 state 前后一致）。

### 本次发现的问题（未修复，记录在案）
1. **前端 OUT_OF_SCOPE 无提示（轻微缺陷）**：`static/js/app.js` 的 `sendMessage` 只在响应含 `chatId` 时调用 `updateTopicStatus`，而 OUT_OF_SCOPE 响应无 chatId，导致"已拒答"提示不显示。建议将 `updateTopicStatus(data.topicAction)` 移出 `if (data.chatId)` 分支。
2. **TopicRouter 判定不稳定（遗留风险实锤）**：本地 qwen3.5:4b 对同一问题在不同时间给出不同判定——"纯棉T恤会缩水吗？"一次 NEW_TOPIC 正常回答、一次 CLARIFY 澄清；无上下文"它怎么洗？"一次直接回答通用洗涤建议、一次误判 OUT_OF_SCOPE 拒答。需要上线后持续观察或升级路由模型/增加规则兜底。

### 遗留事项 / 待办
- 生产环境持续观察：主题切换准确率、摘要失败率（本次实测已见 1 次 JSON 解析失败降级）、长期记忆误用率、无关问题误回答率。
- 建议修复前端 OUT_OF_SCOPE 提示缺陷（见上）。
- `e2e_user_4` 的 `size=L` 长期偏好为步骤5接口测试所删（预期行为），测试用户 `e2e_user_*`/`browser_test_*` 及 anonymous 浏览器测试会话保留作验证证据。

---

## [2026-08-23] 长期偏好按意图筛选 + 回归测试补齐

### 改动标题
长期偏好从“全量注入”改为“按当前问题/意图筛选后注入”，并补齐方案测试计划中缺失的回归测试

### 改动文件清单
修改：
- `services/memory_service.py` — 新增 `select_for_query()`：按 `size/color/material/wearing_restriction` 四类触发词筛选；命中推荐/选购/搭配等购物意图时四类一起注入；显式 `intent` 可精确限定单类
- `services/chat_service.py` — Agent 上下文只接收筛选后的偏好，路由阶段仍使用全量偏好；`_update_summary()` 增加异常兜底，摘要模型抛错绝不影响本轮回答
- `tests/test_memory_service.py`（新建）— 偏好筛选四类场景、`anonymous` 不写记忆、低置信度不写入
- `tests/test_chat_service_memory.py` — 新增 CONTINUE 复用主题、首轮建会话建主题、摘要失败不影响主流程、摘要版本冲突不覆盖、越界不入摘要/记忆、Agent 只收筛选后偏好
- `tests/test_chat_api.py` — 新增响应含 `topicId/topicAction`、越界响应兼容、消息接口只暴露旧字段
- `tests/test_migration_script.py`（新建）— 迁移脚本关键步骤静态守护（真实执行仍需 PostgreSQL）
- `README.md` — 偏好注入说明同步为“按当前问题/意图筛选”

### 关键设计决策与理由
1. 筛选放在 `MemoryService` 的纯函数方法里，不增加额外模型调用，路由仍能看到全部偏好以判断主题边界。
2. 推荐/选购类问题视为通用服装场景，四类偏好都有参考价值；洗护、尺码等具体问题只注入命中类别，避免“尺码”偏好在洗护问题里串用。
3. `_update_summary` 原先只依赖 `SummaryService` 内部捕获异常，现在在调用层也兜底，语义上真正满足“摘要失败不影响本轮回答”。

### 遗留事项 / 待办
- 真实 PostgreSQL 迁移与端到端验证仍需在具备数据库和模型服务的环境执行；迁移脚本测试目前为静态守护。

### 验证结果
- `pytest tests/`：43 passed, 1 warning（第三方 LangGraph 弃用提示）
- 改动文件 `py_compile`：全部通过

---

## [2026-08-23] 企业级会话记忆升级：复检收尾与真实环境边界确认

### 改动标题
本任务是“企业级会话记忆升级执行方案”的最后一轮收尾：确认代码与服务路由真实落地，明确哪些验证在当前环境完成、哪些必须依赖数据库与模型服务。

### 改动文件清单
本次仅修改：
- `changelog.md` — 追加本条最终验证记录

无需改动 `README.md`、`AGENTS.md`，会话记忆、主题路由、长期记忆、API Key 鉴权等内容已在上一条记录同步到文档。

### 关键设计决策与理由
1. **代码主体已在前几轮完成**：`conversation_topics`/`memory_items` 模型、TopicRouter、ContextBuilder、SummaryService、MemoryService、主题/长期记忆 API 均已实现，`tests/` 覆盖主题路由、上下文隔离、拒答过滤、记忆开关边界、鉴权、chatId 校验与连接串编码。
2. **服务已加载新路由**：OpenAPI 实际包含 `/api/chat/{conversation_id}/topics`、`/api/chat/{conversation_id}/topics/{topic_id}`、`/api/chat/{conversation_id}/topics/{topic_id}/archive`、`/api/memory`、`/api/memory/{memory_id}`，说明 `main:app` 已接上新代码。
3. **前端 XSS 已根治**：`static/js/app.js` 与 `static/index.html` 均无 `innerHTML`/`insertAdjacentHTML`/内联事件；历史、文件列表、消息气泡均为 DOM + `textContent`。
4. **数据库连接失败确认是网络权限问题**：`/api/conversations` 返回 500，堆栈为 `OSError: [Errno 10013] Connect call failed ('192.168.245.120', 5432)`，即当前环境无法访问该内网 PostgreSQL 地址，并非代码缺陷。

### 遗留事项 / 待办（必须在具备完整依赖的环境执行）
- PostgreSQL 迁移：在测试/生产数据库执行 `scripts/migrate_conversation_memory.sql`（启用 `pgcrypto`、建表、扩展 `messages`、为存量会话建默认主题、按时间生成 `turn_id`、旧拒答消息标记不可进入上下文）。
- 真实模型端到端：DeepSeek / SiliconFlow / Ollama 服务未在当前环境连通，主题路由、滚动摘要、长期偏好提取、主题切换准确率均未实测。
- 浏览器级手动验收：上传含 HTML 文件名（如 `<img onerror=...>.txt`）后文件列表应纯文本显示不执行脚本；设置 API Key 后的 401/200 行为。
- 生产上线后重点观察主题切换准确率、摘要失败率、长期记忆误用率与无关问题误回答率。

### 验证方式与结果
- `pytest tests/`：24 passed, 2 warnings（警告均为第三方 LangGraph 弃用提示与 `.pytest_cache` 权限提示，不影响结果）。
- `py_compile` 全源码 58 个 `.py` 文件：全部通过，退出码 0。
- `git diff --check`：仅 LF/CRLF 换行提示，无空白错误。
- 前端安全扫描：`innerHTML` / `insertAdjacentHTML` / 内联 `onclick` / `document.write` 均为 0。
- 服务已启动于 `http://127.0.0.1:8000`（`--reload`），`/`、`/docs`、`/static/index.html`、`/static/js/app.js` 均返回 200；OpenAPI 新路由齐全。
- 环境限制：`.venv` 内 Python 无法创建进程，`uv run` 因 `E:\Cache\uv_cache` 权限被拒，改用 `D:\MiniAnaconda\python.exe` + `PYTHONPATH` 指向 `.venv\Lib\site-packages` 启动服务。

---

## [2026-08-22] 企业级会话记忆：首轮长期偏好与主题消息边界修复

### 改动标题
修复新会话未注入用户偏好，以及主题上下文放过无主题消息的问题

### 改动文件清单
修改：
- `services/chat_service.py` — 无论是否已有 `chatId`，都按用户身份加载可用长期偏好
- `services/context_builder.py` — active topic 上下文只接受 `topic_id` 严格匹配的消息
- `tests/test_chat_service_memory.py` — 增加新会话加载已有用户偏好的回归测试
- `tests/test_context_builder.py` — 增加无主题消息不得混入当前主题的回归测试

### 关键设计决策与理由
1. 长期偏好属于用户级记忆，不应依赖当前会话是否已经创建；这样新会话的首轮服装推荐也能使用明确的尺码、颜色和面料偏好。
2. active topic 是上下文隔离边界，`topic_id=NULL` 的历史消息不具备主题归属，不能因为兼容旧数据而进入当前主题 Prompt。

### 遗留事项 / 待办
- PostgreSQL 迁移、真实模型服务和前端浏览器级 XSS 验收仍需在具备完整运行依赖的环境执行。

### 验证方式与结果
- 待重新运行 `pytest tests`、源码 `py_compile` 和服务接口检查。

---

## [2026-08-22] 企业级会话记忆：补充首轮偏好回归测试替身

### 改动标题
完善长期记忆 fake service，使新会话偏好注入测试覆盖完整主流程

### 改动文件清单
修改：
- `tests/test_chat_service_memory.py` — 为 fake memory service 补充 `extract_and_save` 空实现，并断言偏好进入 Agent 上下文

### 关键设计决策与理由
1. 测试替身补齐生产服务协议，避免测试在回答完成后的记忆写入阶段因替身缺少方法而误失败。
2. 回归测试同时验证用户偏好被读取和实际传入 Agent，而不是只验证读取调用发生。

### 遗留事项 / 待办
- PostgreSQL 迁移、真实模型服务和前端浏览器级 XSS 验收仍需在具备完整运行依赖的环境执行。

### 验证方式与结果
- 待重新运行完整 pytest 和源码编译检查。

---

## [2026-08-22] 企业级会话记忆升级：记忆开关边界与迁移健壮性

### 改动标题
关闭会话记忆时保持基础消息链路，并增强迁移脚本对 UUID 默认函数的兼容性

### 改动文件清单
修改：
- `db/conversation_repo.py` — `create_conversation` 支持按需不创建主题；`add_turn` 支持无主题消息
- `services/chat_service.py` — 记忆开关关闭时不创建/读取/更新主题和摘要
- `scripts/migrate_conversation_memory.sql` — 显式启用 `pgcrypto`
- `tests/test_chat_service_memory.py` — 增加记忆关闭边界测试并同步测试存储
- `README.md` — 补充记忆开关关闭后的实际行为与迁移依赖
- `AGENTS.md` — 同步企业级会话记忆、测试和前端安全规则

### 关键设计决策与理由
1. 将主题创建作为会话创建的可选行为，避免关闭记忆开关后产生无意义的主题数据。
2. 保留消息落库能力，确保配置降级只影响记忆模块，不破坏基础问答与审计记录。
3. 迁移脚本显式启用 `pgcrypto`，使 `gen_random_uuid()` 的依赖在新数据库上更明确。

### 遗留事项 / 待办
- PostgreSQL 迁移和真实服务端到端验证仍需在具备数据库与模型服务的环境执行。
- 生产环境需重点观察主题切换准确率、摘要失败率和长期记忆误用率。

### 验证方式与结果
- `pytest tests`：22 passed, 1 warning。
- 新增边界验证：关闭 `conversation_memory_enabled` 时不创建主题、不初始化长期记忆服务，基础消息仍可落库。
- `py_compile`、服务启动与 `/docs`/静态首页检查仍待完成。

---

## [2026-08-22] 企业级会话记忆升级：测试收尾与主题详情接口修复

### 改动标题
修复主题详情响应构造，并让异步主流程测试不依赖 pytest-asyncio

### 改动文件清单
修改：
- `api/chat.py` — 主题详情接口使用 `TopicListItem.model_dump()` 构造 `TopicDetailResponse`，避免 Pydantic 对象被错误当作字典展开
- `tests/test_chat_service_memory.py` — 使用标准库 `asyncio.run()` 执行异步测试
- `tests/test_topic_api.py` — fake repository 复用主题并统一 UUID 字符串比较

### 关键设计决策与理由
1. 主题详情保持现有响应字段与摘要展示规则，只修复 Pydantic 模型到详情模型的转换方式。
2. 测试使用标准库异步运行器，适配当前项目未安装 `pytest-asyncio` 的开发环境，不增加额外依赖。

### 遗留事项 / 待办
- PostgreSQL 迁移和真实服务端到端验证仍需在具备数据库与模型服务的环境执行。
- 生产环境需重点观察主题切换准确率、摘要失败率和长期记忆误用率。

### 验证方式与结果
- 修复后完整测试：`21 passed, 1 warning`。
- 警告来自第三方 LangGraph 弃用提示，不影响项目测试结果。

---

## [2026-08-23] 安全与正确性优化：API Key 鉴权 / 前端 XSS 修复 / chatId 400 / 连接串编码

### 改动标题
补齐 API Key 鉴权、修复前端存储型 XSS、无效 chatId 返回 400、数据库连接串密码 URL 编码

### 改动文件清单
新建：
- `core/security.py` — `require_api_key` FastAPI 依赖（`X-API-Key` 校验）
- `tests/test_security.py`、`tests/test_chat_api.py`、`tests/test_db_url.py` — pytest 测试

修改：
- `core/config.py` — `EnvConfig` 新增 `API_KEYS`（逗号分隔，默认空串）
- `api/chat.py`、`api/documents.py` — router 级挂载鉴权依赖；`chatId` 无效由 500 改为 400
- `services/chat_service.py` — `process_message` 接收 API 层已校验的 `UUID | None`
- `db/engine.py`、`rag/vector_store.py` — 改用 `sqlalchemy.engine.URL.create()` 构造连接串，密码特殊字符自动编码
- `static/index.html`、`static/js/app.js`、`static/css/style.css` — 设置弹窗新增 API Key 保存；动态渲染全部改为 DOM + `textContent`；内联 `onclick` 改为事件委托；统一 `apiFetch` 携带 `X-API-Key`
- `pyproject.toml` — 新增 dev 依赖组 pytest 与 `[tool.pytest.ini_options]`
- `README.md`、`AGENTS.md` — 鉴权配置与接口说明同步

### 关键设计决策与理由
1. **`API_KEYS` 未配置时放行**：保证本地开发与存量部署不受影响；配置后缺失/错误 key 一律 401，用 `hmac.compare_digest` 防时序攻击。
2. **XSS 根治为纯文本渲染**：文件列表、聊天历史、消息气泡全部改为 DOM 节点 + `textContent`，用户消息/AI 回答不再解析 Markdown 为 HTML（`white-space: pre-wrap` 保留换行）。
3. **chatId 校验前置到 API 层**：与取消息/删除会话接口的 400 语义一致，避免 `ValueError` 落进全局 500 处理器。
4. **连接串统一 `URL.create`**：同步（psycopg）与异步（asyncpg）两套驱动共用同一编码模式，密码含 `@ : /` 不再断连。
5. **顺带修复 renderMessages 消息重复 bug**：历史加载改为直接构建 DOM，不再经 `addMessage` 二次 push 到 `state.messages`。

### 待办
- 浏览器级手动验证 XSS：上传文件名含 HTML 的文件后，文件列表应显示纯文本且不执行脚本。
- 生产部署建议将 `API_KEYS` 从密钥管理注入，不在前端明文展示（当前仅存 localStorage 供内部工具使用）。

### 验证结果
- `py_compile`：改动文件全部通过 ✅
- `pytest tests/`：8 passed ✅（鉴权三种状态、空消息/无效 chatId/合法 chatId、两类连接串编码）
- 双实例实测：未配置 `API_KEYS` 时接口放行；配置后无 key 401、错误 key 401、正确 key + 空消息 400、正确 key + 无效 chatId 400 ✅
- 服务已启动于 http://127.0.0.1:8000，首页 `/docs`、`/static/js/app.js`、`/static/css/style.css` 均 200 ✅

---

## [2026-06-26] 三层防乱说话架构落地（服装垂直客服）

### 改动标题
服装行业垂直客服 L1 检索阈值+Rerank / L2 Prompt 约束 / L3 兜底分类器

### 改动文件清单
新建：
- `rag/model/reranker.py` — SiliconFlow /v1/rerank HTTP 客户端（bge-reranker-v2-m3）
- `services/guard_service.py` — L3 兜底分类器（独立轻量模型 + JSON 解析 + 越界替换）
- `prompts/guard_prompt.txt` — 分类器 prompt（IN_SCOPE/OUT_OF_SCOPE/REFUSAL 三分类 + few-shot）
- `prompts/refusal_template.txt` — 统一拒答话术（L1/L2/L3 共用，保证一致性）

修改：
- `rag/model/factory.py` — 加 `get_reranker()`、`get_guard_model()`
- `rag/vector_store.py` — 加 `search_with_scores()`（暴露 PGVector 余弦距离）
- `rag/rag_service.py` — `retriever_docs` 接入阈值过滤+rerank；`rag_summarize` 空上下文返回拒答哨兵
- `prompts/main_prompt.txt` — 重写为服装垂直客服：服务领域边界+越界清单+拒答模板+3 条 few-shot
- `prompts/rag_summarize.txt` — 增领域限定规则与空上下文拒答规则
- `services/chat_service.py` — agent 执行后接入 `GuardService.check`，越界替换为拒答模板
- `utils/prompt_loader.py` — 加 `load_guard_prompts()`、`load_refusal_template()`
- `config/pgvector.yml` — 加 `candidate_k: 10`、`max_distance: 0.55`
- `config/rag.yml` — 加 `rerank_model_name`、`rerank_top_n: 3`、`guard_model_name: qwen-turbo`
- `config/prompts.yml` — 加 `guard_prompt_path`、`refusal_template_path`
- `AGENTS.md` — 增"进度日志"小节

### 关键设计决策与理由
1. **Rerank 选 SiliconFlow /v1/rerank**：复用现有 `SILICONFLOW_API_KEY`，与默认嵌入模型 bge-m3 同源，bge-reranker-v2-m3 中文效果好。用 httpx 封装（langchain 未内置 SiliconFlow rerank）。
2. **距离阈值用 max_distance 而非 similarity**：PGVector `similarity_search_with_score` 返回余弦距离 ∈ [0,2]（越小越相似），方向与 cosine similarity 相反，配置项命名为 max_distance 避免方向混淆。
3. **兜底分类器用轻量 guard_model（qwen-turbo）**：每次问答多一次 LLM 调用，用小模型控制延迟与成本；与 ChatTongyi 同厂商 DashScope，API key 体系一致。
4. **L3 形态：独立分类器 + 越界替换拒答模板**：不改 agent 输出协议，与现有 ReactAgent 解耦；解析失败默认 IN_SCOPE 放行，避免误杀正常回答。
5. **拒答模板唯一化**：L1 哨兵、L2 prompt、L3 guard 三处引用同一 `refusal_template.txt`，避免 L3 把 L2 的合规拒答误判为越界。
6. **Agent 单例约束遵循**：`GuardService` 也做成 `lru_cache(maxsize=1)` 进程级单例，与 `ReactAgent`、`RagService` 同模式。

### 遗留事项 / 待办
- `config/pgvector.yml` 的 `max_distance: 0.55` 为初始经验值，**需上线后用真实问答集调参**：抽 50 条无关问题 + 50 条相关问题，找使"无关拦截率/相关召回率"最优的阈值。
- L3 guard 分类器有约 200-500ms 额外延迟，若延迟敏感可评估缓存重复问题或改为异步。
- `schemas/chat.py` 未加 `guarded` 字段（按需追加，前端如需展示"已被安全过滤"再改）。
- 尚未接入 L2 的"强制工具先验"硬约束（目前靠 prompt 软约束），如需更强保证可在 `react_agent.py` 加 middleware 校验是否调用过 rag_summarize。

### 验证方式与结果
- 逐文件 `uv run python -m py_compile`：全部通过。
- `from rag.rag_service import RagService` 导入：通过。
- `from services.guard_service import GuardService; GuardService()` 初始化（含真实 LLM 客户端）：通过。
- `from services.chat_service import ChatService` 导入：通过。
- `load_refusal_template()` 内容校验：长度 50，以"抱歉"开头、以"该问题。"结尾，正确。
- 待人工验证：启动服务后用三类问题手测 `/api/chat/`（入域/越界/边界），检查 `logs/` 中 monitor_tool 与 GuardService 日志。

---

## [2026-06-26] 修复 guard 分类器模型路由与标签解析

### 改动标题
guard 分类器从 DashScope 改走 SiliconFlow；标签简化为 IN/OUT/REFUSE + 模糊解析

### 问题背景
- 初版 `get_guard_model()` 用 `ChatTongyi`（DashScope），但 `guard_model_name` 配的 `Qwen/Qwen3.5-4B` 是 SiliconFlow 格式，DashScope 报 `400 Model not exist`。
- 改走 SiliconFlow 后，`Qwen/Qwen3.5-4B` 是思考型模型，chat 端点 60s 超时（嵌入/rerank 端点正常）。
- 换 `Qwen/Qwen2.5-7B-Instruct`（非思考型，0.8s 响应）后，模型输出标签拼写错乱（`OUT_OUT_SCOPE`、`OUTOUSScope`），JSON 格式损坏，解析失败导致越界回答被放行。

### 改动文件清单
修改：
- `rag/model/factory.py` — `get_guard_model()` 从 `ChatTongyi` 改为 `ChatOpenAI(base_url=SiliconFlow, api_key=SILICONFLOW_API_KEY)`
- `config/rag.yml` — `guard_model_name` 从 `Qwen/Qwen3.5-4B` 改为 `Qwen/Qwen2.5-7B-Instruct`，注释更新
- `prompts/guard_prompt.txt` — 标签从 `IN_SCOPE/OUT_OF_SCOPE/REFUSAL` 简化为 `IN/OUT/REFUSE`，强调"只能填这三个值"
- `services/guard_service.py` — `_parse_label()` 重写：三级解析（JSON→正则→裸文本模糊匹配），`_normalize()` 函数将模型输出模糊归一化（含 REFUS/OUT/IN 子串即匹配），优先级 OUT > REFUSE > IN

### 关键设计决策与理由
1. **guard 走 SiliconFlow 而非 DashScope**：模型名 `组织/模型` 格式是 SiliconFlow 体系，与 rerank/embed 同源复用 `SILICONFLOW_API_KEY`，避免 DashScope 与 SiliconFlow 模型名不匹配问题。
2. **选 Qwen2.5-7B-Instruct 而非 Qwen3.5-4B**：Qwen3.5 系列为思考型（thinking）模型，推理块过长导致超时（即使传 `enable_thinking=false` 也无效）；Qwen2.5-7B-Instruct 是非思考型，0.8s 返回，适合每次问答都调用的兜底分类器。
3. **标签简化为 IN/OUT/REFUSE**：7B 模型对长标签 `OUT_OF_SCOPE` 拼写不稳定（出现 `OUT_OUT_SCOPE`/`OUTOUSScope`），短标签更易正确输出。
4. **模糊解析三级兜底**：JSON 解析 → 正则匹配 `"field":"VALUE"` → 裸文本子串匹配。`_normalize()` 用子串匹配（`"OUT" in v`）容忍拼写错误，优先级 OUT > REFUSE > IN 确保越界不被漏判。

### 验证结果
- `py_compile`：通过。
- 真实 SiliconFlow 调用三类场景全部正确：
  - 越界（股票问题+股票回答）→ `label=OUT` → `(False, 拒答模板)` ✅
  - 入域（T恤洗护+洗护回答）→ `label=IN` → `(True, 原回答)` ✅
  - 拒答（编程问题+标准拒答话术）→ `label=REFUSE` → `(True, 原回答)` ✅

---

## [2026-06-26] 修复 Few-shot 示例污染与思考过程暴露

### 改动标题
main_prompt 修复：示例4 幻觉污染 + 思考/行动过程泄露给用户

### 问题背景
1. **示例污染**：上一版示例4 含"今天晚上吃什么 + 身高165体重50kg尺码"，当用户只问尺码问题时，模型把示例中的"今天晚上吃什么"幻觉进自己的思考，误判用户输入含两个问题。
2. **思考过程暴露**：prompt 要求"必须输出真实的自然语言思考过程"，且示例用"思考：/行动：/观察："格式，导致模型把 ReAct 内部推理当作最终回答输出给用户，用户看到的不是答案而是"思考：… 行动：调用 rag_summarize…"。

### 改动文件清单
修改：
- `prompts/main_prompt.txt` — 输出规则重写 + 示例全部重构 + 示例4 换场景 + 加反污染指令

### 关键设计决策与理由
1. **输出规则改为"内部思考"**：将"必须输出思考过程"改为"思考推理在内部完成，不要将过程性内容输出给用户"，并明确"最终回答只包含给用户看的内容"。ReAct 的 think-act-observe 循环由 LangGraph create_agent 内部处理，模型不需要输出文本形式的思考。
2. **示例格式重构**：所有 few-shot 从"思考：/行动：/观察：/回答："改为"（内部判断：…）/（调用…）/最终回答：…"，用括号标注内部步骤，"最终回答："明确标记用户可见内容。
3. **示例4 换场景**：从"今天晚上吃什么+尺码"改为"大盘走势+羽绒服洗不跑绒"，域内问题选冷门场景（羽绒服洗护），避免与常见单问题（尺码咨询）模式匹配导致污染。
4. **反污染指令**：在 Few-shot 小节加引用块"不要将示例中的问题内容注入对真实用户输入的判断——只根据用户实际发送的内容进行分析"。

### 验证结果
- `load_system_prompts()` 内容校验：旧思考规则已移除、新内部规则存在、示例4 不含"今天晚上吃什么"、含新场景"大盘走势+羽绒服"、反污染指令存在。

---

## [2026-06-26] 修复 L1 检索误删相关文档（向量阈值过滤顺序错误）

### 改动标题
L1 检索流程重构：去掉 rerank 前的向量距离阈值过滤，改为 rerank 后用 rerank score 阈值过滤

### 问题背景
域内相关问题也被拒答。诊断发现：`max_distance=0.55` 的向量距离阈值在 rerank **之前**执行，把 rerank 认为高度相关的文档提前删除了。实测数据：
- query "春季纯棉T恤怎么洗涤"：相关文档"纯棉材质洗涤" rerank score=**0.982**，但向量距离=0.634 > 0.55 → 被阈值删除 → 空上下文 → 拒答哨兵
- query "身高165尺码"：相关文档 rerank=0.949，向量距离=0.281 → 恰好通过
根因：向量相似度对语义匹配不够准（最相关文档反而距离更大），在 rerank 前过滤会误删。

### 改动文件清单
修改：
- `rag/rag_service.py:retriever_docs` — 去掉向量距离阈值过滤，改为：向量宽松召回 candidate_k → rerank 精排 → rerank score >= rerank_score_min 过滤
- `config/pgvector.yml` — 删除 `max_distance` 配置项
- `config/rag.yml` — 新增 `rerank_score_min: 0.3`（实测：强相关 >0.9，弱相关 0.3-0.8，不相关 <0.05）

### 关键设计决策与理由
1. **向量阈值过滤改为 rerank 后过滤**：向量相似度只负责宽松召回（candidate_k=10 不过滤），rerank 模型（bge-reranker-v2-m3）专门做 query-document 相关性精排，分数更准。这是标准 RAG 做法（recall → rerank → filter）。
2. **rerank_score_min=0.3**：实测相关文档 rerank score 在 0.34-0.99 之间，不相关文档 <0.05，0.3 能有效区分且留有余量。
3. **保留 rerank 失败降级**：rerank HTTP 异常时退化为向量检索 top_n（不加阈值），保证可用性。

### 验证结果
- `py_compile`：通过。
- 端到端 L1 检索测试：
  - "春季纯棉T恤怎么洗涤"（之前被误删）→ 返回 2 个相关文档（纯棉洗涤、针织棉洗涤）✅
  - "身高165体重50kg穿多大尺码" → 返回 2 个相关文档（尺码表）✅
  - "今天股票涨了吗"（域外）→ 0 文档 → 拒答哨兵 ✅

---

## [2026-06-26] 修复会话历史污染（拒答过的无关问题被补答）

### 改动标题
main_prompt 增"只回答当前最新消息"规则 + 示例5

### 问题背景
用户先问"今天晚上吃什么"（被拒答），再问"身高165体重50kg适合穿什么尺码"（域内）。AI 回答时把上一轮的"今天晚上吃什么"又拒答了一遍，再回答尺码问题。根因：`aexecute` 把完整历史塞进 messages，模型看到历史中有未回应的无关问题就在当前回答里补答。

### 改动文件清单
修改：
- `prompts/main_prompt.txt` — 核心思考准则新增第1条"只回答当前最新消息"规则；原1-4条顺延为2-5条；新增示例5（历史含已拒答问题，当前消息只回答新问题）

### 关键设计决策与理由
1. **改 prompt 而非改历史机制**：多轮历史对域内追问（如"那它怎么洗"指代上文商品）仍有价值，不能简单截断历史。用 prompt 规则约束模型只关注当前消息，历史仅用于指代消解。
2. **新增示例5**：用真实故障场景（"吃什么"→拒答→"尺码"→只答尺码）作 few-shot，明确演示"历史中的拒答不要在当前回答里重提"。

### 验证结果
- `load_system_prompts()` 内容校验：新规则"只回答用户当前最新这一条消息"存在、示例5存在、含"已被拒答"措辞。

---

## [2026-06-26] 新增 L0 域内预检 + 修复示例污染

### 改动标题
agent 执行前加 L0 域内预检拦截越界问题；删除示例5（含"今天晚上吃什么"导致污染）

### 问题背景
用户问"今天晚上吃什么"，agent 不仅拒答，还幻觉出"夏天适合穿什么衣服"这一问题并调用 rag_summarize 检索回答。根因：
1. 示例5 含"今天晚上吃什么"（与用户输入完全一致），导致 few-shot 污染
2. ReAct agent 有工具就倾向于调用，prompt 说"越界不调工具"但约束不住
3. 模型把越界问题强行联想成服装问题来调用工具

### 改动文件清单
新建：
- `prompts/scope_check_prompt.txt` — L0 域内分类器 prompt（纯文本 IN/OUT 输出，5 条示例）

修改：
- `services/guard_service.py` — 新增 `check_question_scope()` 方法和 `_parse_scope_label()`，复用 guard model + scope prompt；暴露 `refusal_text` 属性
- `services/chat_service.py` — agent 执行前接入 L0 预检，越界直接返回拒答不调 agent
- `utils/prompt_loader.py` — 新增 `load_scope_check_prompt()`
- `config/prompts.yml` — 新增 `scope_check_prompt_path`
- `prompts/main_prompt.txt` — 删除示例5（含"今天晚上吃什么"导致污染）

### 关键设计决策与理由
1. **L0 代码级拦截优于 prompt 约束**：ReAct agent 有工具就倾向于调用，prompt 说"不调工具"不可靠。L0 预检在 agent 之前执行，越界问题根本不进入 agent，从源头杜绝工具误调。
2. **域内分类用纯文本 IN/OUT 而非 JSON**：Qwen2.5-7B-Instruct 输出 JSON 时格式混乱（字符间插入引号空格），改为纯文本输出只需匹配 "OUT"/"IN" 子串，解析更可靠。
3. **删除示例5**：示例5 含"今天晚上吃什么"与真实用户输入完全一致，导致模型把示例上下文混入真实对话。历史污染问题改由 L0 预检 + 核心思考准则第1条"只回答当前最新消息"共同解决。
4. **解析失败默认 IN**：避免误拦正常服装问题，域内问题交给 agent + L3 兜底双重保障。

### 验证结果
- `py_compile`：全部通过。
- L0 预检四类问题全部正确：
  - "今天晚上吃什么" → OUT → 拦截 ✅
  - "身高165体重50kg穿多大尺码" → IN → 放行 ✅
  - "今天大盘涨了吗" → OUT → 拦截 ✅
  - "纯棉T恤怎么洗" → IN → 放行 ✅

---

## [2026-06-26] L0 预检输出改为 YES/NO 避免子串冲突

### 改动标题
scope_check_prompt 输出从 IN/OUT 改为 YES/NO；解析器对应调整

### 问题背景
"夏天穿什么衣服合适"等穿搭问题被 L0 误判为越界拒答。根因：`_parse_scope_label` 用 "OUT" in text 优先于 "IN" in text，若 7B 模型输出带解释（如"IN，非OUT"），"OUT" 子串会命中导致误判为越界。IN/OUT 两个词互含对方字母（OUT 中的 O/U/T 与 IN 无交集，但模型可能输出混合文本）。

### 改动文件清单
修改：
- `prompts/scope_check_prompt.txt` — 输出标签从 IN/OUT 改为 YES/NO（互不包含子串，彻底避免冲突）；增加穿搭/季节/颜色正面示例
- `services/guard_service.py:_parse_scope_label` — 改为匹配 YES→IN / NO→OUT

### 关键设计决策与理由
1. **YES/NO 替代 IN/OUT**：YES 和 NO 互不包含对方子串，即使模型输出带解释也不会误匹配。
2. **增加穿搭正面示例**：prompt 新增"夏天穿什么衣服合适""黑皮肤适合穿什么颜色""冬天羽绒服怎么洗"等穿搭类 YES 示例，强化 7B 模型对穿搭问题的域内判断。
3. **解析顺序 YES 优先**：先匹配 YES（放行），再匹配 NO（拦截），确保域内问题不被误拦。越界误放行有 agent prompt + L3 兜底，危害远小于域内误拦。

### 验证结果
- `py_compile`：通过。
- 8 类问题测试：5 个域内（夏天穿搭/冬天穿搭/肤色配色/尺码/洗护）全部正确放行 ✅；2 个越界（饮食/股票）正确拦截 ✅；1 个越界（编程）误放行（有 L3 兜底，可接受）。

---

## [2026-06-26] rag_summarize 改为返回原文资料，匹配分析交由 agent

### 改动标题
rag_summarize 不再调用 LLM 做总结，直接返回检索到的原文片段；agent 自行分析匹配

### 问题背景
尺码问题"身高165体重50kg穿多大尺码"被拒答。日志显示 rag_summarize 返回"无匹配尺码建议"。根因：rag_summarize 调用 LLM（ChatTongyi）对尺码表做匹配总结时，LLM 不做 kg→斤换算（50kg=100斤），或只看第一条区间就放弃，不稳定（3次测试分别返回 M、S、"未匹配"）。二次 LLM 调用引入不稳定性。

### 改动文件清单
修改：
- `rag/rag_service.py:rag_summarize` — 去掉 `self.chain.invoke()`（LLM 总结），改为直接拼接返回原文资料片段
- `prompts/main_prompt.txt` — rag_summarize 工具描述更新：明确"返回原文资料（非总结）"，要求 agent 自行分析匹配（含 kg/斤换算）
- `prompts/rag_summarize.txt` — 增单位换算与逐条匹配规则（保留备用，当前 rag_summarize 不再调 LLM）

### 关键设计决策与理由
1. **rag_summarize 只检索不总结**：原来 rag_summarize = 检索 + LLM 总结，二次 LLM 调用不稳定（尺码匹配时对单位换算和逐条匹配不可靠）。改为只返回原文，让 agent（qwen3.7-max，更强的模型）自己做匹配分析，减少一次 LLM 调用且提高准确性。
2. **agent prompt 明确匹配职责**：main_prompt 工具描述新增"需逐条匹配资料区间，注意 kg 与斤换算"，让 agent 知道它需要自己做单位换算和区间匹配。
3. **rag_summarize.txt 保留**：虽然 rag_summarize 不再调 LLM，但保留 prompt 文件以备未来恢复或独立使用。

### 验证结果
- `py_compile`：通过。
- `rag_summarize("身高165 体重50kg 尺码建议")` 返回原文尺码表（含 90-115斤→M码区间），agent 可自行匹配 100斤→M码 ✅。
- 检索结果稳定（不再依赖 LLM 波动）✅。

---

## [2026-06-26] 代码级过滤历史拒答问答对，彻底解决会话历史污染

### 改动标题
chat_service 新增 `_filter_refusal_history`，传给 agent 前移除历史中已被拒答的问答对

### 问题背景
用户先问"广州有什么好吃的"（被 L0 拦截拒答），再问"身高165体重50kg适合穿多大尺码"（域内）。agent 回答时仍把"关于广州美食，抱歉…"补答了一遍。根因：`aexecute` 把完整历史（含拒答问答对）传给 agent，agent 看到历史中的拒答就回头处理。prompt 约束（"只回答当前最新消息"）对强模型不够可靠。

### 改动文件清单
修改：
- `services/chat_service.py` — 新增 `_filter_refusal_history()` 函数，在 `process_message` 中获取 history 后调用，移除拒答问答对后再传给 agent

### 关键设计决策与理由
1. **代码级过滤优于 prompt 约束**：prompt 说"不要回头处理历史拒答"对强模型（qwen3.7-max）不够可靠。代码级过滤在传给 agent 前就移除拒答问答对，agent 根本看不到历史中的无关问题，从源头杜绝。
2. **识别 marker 用"暂无法回答该问题"**：所有拒答回答（L0 拦截的 refusal_text、L3 替换的拒答、agent 自身拒答）都包含此关键词，可统一识别。
3. **成对移除**：遇到拒答 AIMessage 时，移除 result 中已加入的配对 HumanMessage，保持历史消息成对完整。
4. **保留正常域内问答历史**：只移除拒答问答对，正常的域内多轮对话（如追问指代消解）仍保留。

### 验证结果
- `py_compile`：通过。
- 过滤逻辑测试：3 条历史（[H:广州美食, AI:拒答, H:尺码问题]）→ 过滤后 1 条（[H:尺码问题]），拒答问答对被正确移除 ✅。

---

## [2026-06-27] 降低 rerank_score_min 从 0.3 到 0.05

### 改动标题
rerank 阈值放宽，解决弱相关查询被全部过滤导致拒答

### 问题背景
"天气比较热，适合穿什么材质的衣服"被拒答。日志显示 rag_summarize 返回拒答模板。诊断数据：
- query "天气热 夏季 适合 材质 面料"：原始向量检索 10 条，最高 rerank=**0.151**（文档"春季服装/纯棉/薄牛仔/轻薄化纤"），被 rerank_score_min=0.3 全部过滤 → 0 条 → 拒答
- query "T恤 洗涤 方法"：最高 rerank=0.981 → 通过
- query "身高165体重50kg"：最高 rerank=0.949 → 通过
根因：知识库缺少专门的"夏季透气面料"内容，最佳匹配文档（春季面料）的 rerank 分只有 0.15，被 0.3 阈值误杀。

### 改动文件清单
修改：
- `config/rag.yml` — `rerank_score_min` 从 0.3 改为 0.05

### 关键设计决策与理由
1. **0.3→0.05**：实测数据分布：强相关 >0.9，弱相关 0.1-0.3（如"天气热 材质 面料"→春季服装=0.15），不相关 <0.05（如尺码表对天气查询=0.001）。
2. 0.05 能通过弱相关文档（0.15>0.05），过滤真正无关内容（0.001<0.05）。
3. 配合 rag_summarize 改为返回原文，agent 自己判断资料相关性，弱相关文档不会导致误回答。

### 验证结果
- 之前返回 0 文档的 4 个查询全部恢复正常：
  - "天气热 夏季 适合 材质 面料" → 1 条（春季面料）✅
  - "T恤 洗涤 方法" → 2 条（含冰丝夏季T恤）✅
  - "夏季 透气 凉爽 面料 推荐" → 2 条 ✅
  - "天气热 适合穿什么材质 面料 夏季 透气" → 1 条 ✅
- 域外查询仍返回 0：股票=0、美食=0 ✅

---

## [2026-06-27] L0 越界拦截不再落库，从源头杜绝历史污染

### 改动标题
L0 预检提前到创建会话之前，越界问题不入库、不创建会话

### 问题背景
用户先问"广州有哪些好玩的地方"被拒答并落库，再问"身高165穿多大尺码"时 agent 仍回头提及"关于广州…"。之前的 `_filter_refusal_history` 过滤方案依赖服务重启且本质是"先污染后治理"，不够可靠。

### 改动文件清单
修改：
- `services/chat_service.py:process_message` — L0 预检移到最前面（`create_conversation` 之前），越界直接返回拒答不入库；保留 `_filter_refusal_history` 作为安全网

### 关键设计决策与理由
1. **L0 提到最前面**：越界问题在创建会话、获取历史、调用 agent 之前就拦截返回，零数据库操作。
2. **越界不创建会话**：`chat_id` 为空的越界请求不创建 conversation，数据库中不会留下空会话。
3. **保留 `_filter_refusal_history`**：处理存量数据（旧拒答记录）和 agent 自主生成拒答的边缘 case。
4. **越界不落库 > 落库后过滤**：源头杜绝优于事后补救，不依赖服务重启或过滤逻辑正确性。

### 验证结果
- `py_compile`：通过。
- `_filter_refusal_history` 安全网验证：2 条历史（H+拒答AI）→ 过滤后 0 条 ✅。

---

## [2026-06-27] README 全面重写，对齐服装垂直客服现状

### 改动标题
README 重写：项目定位改为服装垂直客服，补充三层防乱说话架构、L0/L1/L2/L3 数据流、最新 API 响应格式

### 改动文件清单
修改：
- `README.md` — 全量重写（保留原有结构骨架）

### 关键设计决策与理由
1. **项目定位更新**：从"通用 RAG 问答系统"改为"服装垂直客服"，反映近 10 次迭代后的实际用途。
2. **新增三层架构图**：ASCII 流程图展示用户提问从 L0→L1→L2→L3 的完整流转路径。
3. **API 响应格式修正**：文件列表返回 `chunk_count` 字段，匹配当前 `list_all` JOIN SQL 实现。
4. **移除错误声明**：README 原称"ORM 表启动时自动创建"——代码中无 `Base.metadata.create_all`，改为强调手动建表。
5. **补充配置说明**：新增 `rerank_score_min`、`candidate_k`、`guard_model_name`、`refusal_template_path` 等新配置项。
6. **模型依赖表格化**：主 Agent/Rerank/Guard/嵌入各模型的服务商与 API key 来源一览。

### 验证结果
- `uv run python -m py_compile main.py`：通过。
- 全文检查：README 中的文件路径、配置键名、API 路径均与代码一致 ✅。

---

## [2026-06-27] 修复 L3 兜底误判域内回答为越界（解析鲁棒性 + 历史窗口 + 工具对齐）

### 改动标题
guard_service `_parse_label` 子串匹配误杀修复；历史窗口收紧；main_prompt 工具 query 对齐规则

### 问题背景
同一会话先问"身高170体重55kg适合穿多大尺码"（正常回答），再问"纯棉的衣服该如何洗护"时未能正常回答，最终被替换为拒答模板。诊断证据链：
1. **L3 检查的是回答内容**：`chat_service.py:62` 把 query 和 answer 一起送 guard 模型，日志只打印 query 但实际判定依据是 answer。
2. **agent 被历史污染调了无关工具**：日志显示回答洗护问题时 agent 调了两个工具——`rag_summarize('纯棉衣服洗护 洗涤保养')`（相关）和 `rag_summarize('尺码推荐 身高 体重')`（无关，是上一轮遗留）。`ReactAgent` 是进程级单例，`aexecute` 传入含前两轮的历史，模型受历史 ToolMessage 干扰调了无关工具，最终回答混入尺码内容。
3. **guard 模型误判**：guard 模型是 `Qwen2.5-7B-Instruct`（7B 轻量），对混合内容（洗护+尺码）的合规判断摇摆。
4. **`_parse_label` 解析隐患**：step 3 裸文本兜底用 `"OUT" in upper` 子串匹配，若 guard 模型 reason 里含 "OUT" 字样（如 "not OUT of scope"），JSON 解析失败时会误判为 OUT；`_normalize` 的 `"OUT" in v` / `"IN" in v` 同样是子串匹配，"NOT OUT" / "ABOUT" / "INPUT" 会被误归一化。

根因总结：对话历史污染 → agent 调无关工具 → 回答内容混乱 → 7B guard 误判 OUT → 回答被替换为拒答模板。

### 改动文件清单
修改：
- `services/guard_service.py` — `_normalize()` 从子串匹配改为精确匹配（`v == "OUT"` / `v == "IN"` / `v.startswith("REFUS")`）；step 3 裸文本兜底从子串匹配改为 `\b(OUT|IN|REFUSE|REFUS\w*)\b` 整词匹配；step 1 JSON 解析失败时新增 `_LABEL_FIELD_RE` 直接抽取 `"label"` 字段值；模块级新增 `_LABEL_FIELD_RE`、`_BARE_WORD_RE` 两个预编译正则；docstring 更新
- `config/database.yml` — `max_messages` 从 30 改为 8（约 4 轮上下文），加注释说明历史过大会污染当前问题的工具调用决策
- `prompts/main_prompt.txt` — 核心思考准则新增第 6 条：rag_summarize 的 query 参数必须直接派生自用户当前最新消息，不得参考或复用历史对话中的工具调用参数

### 关键设计决策与理由
1. **P0 精确匹配替代子串匹配**：`_normalize` 改为 `v == "OUT"` 精确匹配，避免 "NOT OUT" / "ABOUT" / "INPUT" 等含子串的文本被误归一化。这是最可能的元凶——当 guard 模型输出 `{"label": "IN", "reason": "answer is not OUT of scope"}` 而 JSON 因尾逗号等小瑕疵解析失败时，旧逻辑 `"OUT" in upper` 会命中 reason 中的 "OUT" 误判为越界。
2. **step 3 整词匹配**：`\bOUT\b` 要求 OUT 前后是非字母字符，"ABOUT"/"INPUT" 中的 OUT/IN 不会被匹配。裸文本兜底本就是异常路径（prompt 要求只输出 JSON），倾向保守判 IN。
3. **step 1 JSON 失败时优先抽 label 字段**：新增 `_LABEL_FIELD_RE` 在 JSON 解析失败时直接抽取 `"label":"VALUE"`，比 step 2 的宽泛字段正则（兼容 label/fit/result 等）更精准，避免匹配到 reason 中出现的字段名。
4. **P1 历史窗口 30→8**：`max_messages=30` 对单轮问答场景过大，前几轮的"尺码推荐"上下文会污染当前"洗护"问题的工具调用决策。8 条（约 4 轮）足以解决"它/上面那个"指代问题。`max_tokens=2000` 保持不变。
5. **P2 prompt 工具对齐规则**：现有 prompt 已强调"只回答当前最新消息"，但未显式约束工具调用 query 必须源自当前问题。新增第 6 条明确禁止工具 query 漂移到历史话题（如当前问洗护，禁止传"尺码/身高/体重"检索词）。
6. **不做 P3（升级 guard 模型）**：先验证 P0+P1+P2 效果，若仍误判再换 14B/8B 非思考模型，避免引入额外延迟。

### 遗留事项 / 待办
- P3（guard 模型升级到 Qwen2.5-14B-Instruct 或 Qwen3-8B 非思考型）留作后续验证后再决定。
- 待人工端到端验证：启动服务复现日志场景（同会话先问尺码再问洗护），确认 L3 输出 `label=IN` 且 agent 不再调用尺码相关工具。
- 回归用例待跑："今天晚上吃什么"→L0 OUT 拦截；"今天大盘涨了吗"→L3 OUT/REFUSE 拒答；"纯棉T恤会缩水吗"→L3 IN 正常回答。

### 验证结果
- `uv run python -m py_compile services/guard_service.py`：通过 ✅
- `uv run python -m py_compile services/chat_service.py`：通过 ✅
- `uv run python -m py_compile db/conversation_repo.py`：通过 ✅
- `_parse_label` 13 个用例单元验证全部通过 ✅，关键回归用例：
  - `'{"label": "IN", "reason": "answer is not OUT of scope"}'` → IN（旧逻辑会误判 OUT）✅
  - `'{"label": "OUT", "reason": "finance question"}'` → OUT ✅
  - `'{"label": "REFUSE", "reason": "refusal template"}'` → REFUSE ✅
  - `'ABOUT the INPUT scope'` → IN（整词匹配不命中 ABOUT/INPUT 中的子串）✅
  - `'{"label": "OUT",}'`（尾逗号 JSON 畸形）→ OUT（走 `_LABEL_FIELD_RE` 兜底）✅
  - `'random text with no label keyword'` → IN（默认放行）✅

---

## [2026-06-27] P0-P2 验证失败，代码级根治历史污染（不传历史给 agent）

### 改动标题
chat_service 新增 `_limit_history_turns` + `agent_history_turns` 配置项，默认不传历史

### 问题背景
上一轮 P0（解析鲁棒性）+ P1（max_messages 30→8）+ P2（prompt 工具对齐规则）落地后，"纯棉的衣服该如何洗护"依旧被 L3 判 OUT 拒答。新日志（logs/chunking.log 587-627 行）证据：
```
16:51:12 scope_check 纯棉洗护 label=IN          ← L0 放行
16:51:12 即将调用模型，带有7条消息               ← 历史有6条（3轮累积）
16:51:16 rag_summarize('身高170 体重55kg 尺码推荐')   ← 又调尺码工具！P2 prompt 规则失效
16:51:16 rag_summarize('纯棉衣服洗护保养方法')        ← 相关的
16:51:26 rag_summarize('尺码表 身高160-170 体重90-115斤 M码')  ← 又调尺码！
16:51:37 L3 label=OUT                        ← 回答混入尺码内容，被判OUT拒答
```
根因再确认：
1. **P2 prompt 软约束对 qwen3.7-max 完全失效**：模型看到 history 里上一轮尺码 AI 回答的具体内容，就反复调尺码工具，prompt 第6条规则管不住。
2. **P1 max_messages=8 未生效**：16:51:12 仍带 7 条消息（3 轮历史）。因 `conversation_repo.py:10` 的 `MAX_MESSAGES = db_conf.get(...)` 是模块级常量，服务启动时读一次就固定，改 yml 不重启不生效；即便重启，6 条历史仍 ≤ 8 照单全收。
3. P0 解析修复虽正确但治标不治本：agent 回答确实混入尺码内容（真跑题），guard 判 OUT 是"正确"判定，P0 改不动这个。

结论：历史污染是反复出现的顽疾（changelog 已 5 次相关修复），prompt 约束不可靠，必须代码级根治。

### 改动文件清单
修改：
- `config/database.yml` — 新增 `agent_history_turns: 0` 配置项（默认不传历史），加注释说明权衡；`max_messages` 注释更新为"仅控制 DB 查询量，改此项需重启服务才生效"
- `services/chat_service.py` — 顶部 `from core.config import db_conf`；模块级常量 `_AGENT_HISTORY_TURNS = db_conf.get("agent_history_turns", 0)`；新增 `_limit_history_turns()` 函数（turns<=0 返回空列表，否则保留最近 turns*2 条）；`process_message` 在 `_filter_refusal_history` 之后调用 `_limit_history_turns`

### 关键设计决策与理由
1. **代码级不传历史（turns=0）而非 prompt 约束**：P2 已证明 prompt 软约束对 qwen3.7-max 不可靠。代码级在传给 agent 前就清空历史，agent 根本看不到上一轮 AI 回答内容，从源头杜绝工具调用漂移。这是继 `_filter_refusal_history`（过滤拒答问答对）之后的进一步代码级根治。
2. **默认 turns=0（不传历史）而非 turns=1**：即使只传最近 1 轮，若上一轮是尺码问答，agent 仍会被污染调尺码工具。服装客服场景用户问题大多独立（"纯棉怎么洗护"不依赖上文），多轮指代极少；不传历史最可靠。
3. **保留配置项而非硬编码**：`agent_history_turns` 可调，未来若需多轮指代（"它怎么洗"指代上文商品），改为 1 即可恢复最近 1 轮历史。配置项放在 database.yml 与 max_messages 同组。
4. **保留 `_filter_refusal_history` 与 max_messages**：前者处理存量拒答数据（安全网），后者控制 DB 查询量（虽不影响 agent，但减少序列化开销）。
5. **模块级常量需重启生效**：`_AGENT_HISTORY_TURNS` 在 chat_service 模块加载时读取，改 yml 后需重启服务。已在 database.yml 注释和给用户的说明中强调。

### 遗留事项 / 待办
- **多轮指代能力暂时关闭**：turns=0 时 agent 无历史，用户问"那它怎么洗"（指代上文）将丢失上下文。若实际场景需要，将 `agent_history_turns` 改为 1 并重启服务。
- 待人工端到端验证：重启服务后复现场景（同会话先问尺码再问洗护），确认：
  - "纯棉的衣服该如何洗护" → agent 仅调用洗护相关工具，L3 输出 `label=IN`，正常回答 ✅
  - "身高170体重55kg适合穿多大尺码" → 正常回答（单轮不受影响）✅
  - 回归：越界问题（今天吃什么/大盘）仍被拦截 ✅

### 验证结果
- `uv run python -m py_compile services/chat_service.py`：通过 ✅
- `uv run python -m py_compile services/guard_service.py`：通过 ✅
- `_limit_history_turns` 7 个用例单元验证全部通过 ✅：
  - turns=0 → 0 条（不传历史）✅
  - turns=1 → 2 条（最近1轮），末条为最新 AI 回答 ✅
  - turns=2 → 4 条（最近2轮）✅
  - 空历史 + turns=1 → 0 条 ✅
  - 不足1轮（1条）+ turns=1 → 原样1条 ✅
  - `_filter_refusal_history` 仍正常（拒答问答对被移除）✅
  - 组合（过滤 + turns=0）→ 0 条 ✅

---

## [2026-08-13] 清除全仓库死代码

### 改动标题
移除未使用的函数/成员/导入/配置项与依赖，消除 rag_summarize 重构后遗留的 LLM chain 死代码

### 问题背景
`rag_summarize` 早已改为"只检索不总结"（changelog 2026-06-26），但 `RagService` 仍保留 `self.model/self.chain/self.prompt/self.retriever/_init_chain` 等死成员，每次实例化还额外初始化一个聊天模型客户端。其余仓库散落多处从未被调用的函数与未用导入。整体代码审阅时确认这些均为死代码。

### 改动文件清单
修改：
- `rag/rag_service.py` — 删除 `self.retriever/self.prompt_text/self.prompt/self.model/self.chain/_init_chain()`；清理未用导入（`StrOutputParser`、`PromptTemplate`、`load_rag_prompts`、`get_chat_model`）
- `rag/vector_store.py` — 删除 `get_retriever()`（无调用方；检索走 `search_with_scores`）
- `rag/model/factory.py` — 删除 `get_guard_model()`（无调用方，guard 实际走 `get_ollama_llm`）
- `config/rag.yml` — 删除孤立配置项 `guard_model_name`（其唯一消费者 `get_guard_model()` 已删；且该值为已弃用的 Qwen3.5-4B 思考模型）
- `agent/react_agent.py` — 删除 `execute_stream()` 方法与 `__main__` 测试块；`aexecute` 去掉死参数 `context={"report": False}`；修正 `model=get_chat_model() ,` 多余空格
- `agent/tool/middleware.py` — 删除 `fill_context_for_report` 死分支（工具不存在）；清理未用导入 `dynamic_prompt`、`ModelRequest`
- `rag/query_rewriter.py` — 清理未用导入 `get_guard_model`
- `services/guard_service.py` — 清理未用导入 `get_guard_model`
- `utils/file_handler.py` — 删除 `get_file_md5_hex()`、`listdir_with_allowed_type()`（无调用方）及 `os/hashlib/Optional` 导入
- `utils/prompt_loader.py` — 删除 `load_rag_prompts()`（无调用方）
- `config/prompts.yml` — 删除孤立配置项 `rag_summarize_prompt_path`（其唯一消费者 `load_rag_prompts()` 已删；`prompts/rag_summarize.txt` 文件保留备用）
- `pyproject.toml` + `uv.lock` — 移除从未被 import 的依赖 `streamlit`、`recursivecharactertextsplitter`；`uv lock` 同步（连同其传递依赖 altair/pandas/pillow/pyarrow 等一并移除，111→85 包）

### 关键设计决策与理由
1. **只删无调用方的代码**：所有删除项均经 `grep` 全仓库确认无引用（`get_guard_model`/`get_retriever`/`execute_stream`/`get_file_md5_hex`/`load_rag_prompts` 等），不涉及仍在使用的公共 API。
2. **保留 `prompts/rag_summarize.txt`**：尽管已无 loader 引用，按上次 changelog 决策保留以备未来恢复 LLM 总结；仅删除死函数与死配置项。
3. **`guard_model_name` 一并删除**：`get_guard_model()` 是唯一消费者，且其值 `Qwen/Qwen3.5-4B` 是 changelog 明确记录会 60s 超时的弃用值，删除避免误导后续接线。
4. **依赖移除走 `uv lock` 而非手工编辑 lock**：保证 lockfile 与 pyproject 一致（`uv lock --check` 通过），避免手工删 lock 引入版本漂移。

### 待办
- 剩余非死代码问题（不属于本次范围）：guard/query_rewriter 仍依赖本地 Ollama、`_last_docs` 并发竞态、上传流程跨存储非原子、缺鉴权、同步阻塞调用等，见代码审阅清单。
- 根目录 `session-ses_0fcf.md` 为会话日志残留文件，未在 gitignore 中，建议人工确认后删除。

### 验证结果
- `uv run python -m py_compile` 全部通过 ✅（含 main.py 与所有改动模块）
- `uv lock --check`：通过 ✅（85 包）
- 关键模块导入冒烟测试：`utils.prompt_loader`、`rag.model.factory`、`rag.rag_service`、`services.guard_service`、`services.chat_service`、`agent.react_agent` 等全部 import OK ✅

---

## [2026-08-13] README 全面对齐代码现状

### 改动标题
README 更新：模型路由改为实际接线（DeepSeek 主 Agent + SiliconFlow 嵌入/Rerank + Ollama Guard/QueryRewrite），修正 API 响应示例字段与文档/代码不一致处

### 问题背景
代码审阅发现 README 与实际代码存在多处漂移：主 Agent 文档写 qwen3.7-max(DashScope) 但代码用 deepseek-v4-flash(DeepSeek)；L0/L3 Guard 文档写 SiliconFlow Qwen2.5-7B 但代码用本地 Ollama qwen3.5:4b；文件接口响应字段（`chunks`/`chunk_count`）与实现不符；`rag_summarize_prompt_path`/`guard_model_name`/`openai_chat_model_name` 等配置项已被删除但仍被文档引用。

### 改动文件清单
修改：
- `README.md` — 全量对齐代码现状

### 关键设计决策与理由
1. **按代码实际接线写文档**：主 Agent=DeepSeek `deepseek-v4-flash`；嵌入=SiliconFlow `BAAI/bge-m3`；Rerank=SiliconFlow `BAAI/bge-reranker-v2-m3`；L0/L3 Guard 与 Query Rewrite=本地 Ollama `qwen3.5:4b`。技术栈与模型依赖表、架构图、配置说明（rag.yml/prompts.yml）、环境变量说明同步更新。
2. **明确 Ollama 硬依赖及降级行为**：模型依赖表加注——Ollama 未启动时 L0/L3 静默放行（解析失败默认 IN）、Query Rewrite 回退原始 query；FAQ 新增第 6 条排查指引。
3. **修正 API 响应示例**：上传返回的 `chunks` 实为 chunk id 列表（非计数）；文件列表返回 `chunks`（计数）而非 `chunk_count`，且无 `uploaded_at` 字段。
4. **修正上传流程原子性描述**：向量写入走 PGVector 独立同步连接、`uploaded_files` 走异步 ORM 事务，分属两个事务——README 原文"任一步异常则整体回滚"不成立，改为如实描述并标注孤立向量风险。

### 待办
- 与 README 同步的代码层面遗留：`dashscope` 依赖已无实际 import（ChatTongyi 未使用），可在后续清理中移除；`config/database.yml` 与 `chat_service.py` 注释中仍引用已弃用的 `qwen3.7-max`。
- README 中已如实记录 guard 走本地 Ollama；若后续改回 SiliconFlow guard（changelog 历史意图），需同步更新模型依赖表。

### 验证结果
- 全文 grep 校验：README 不再残留 `qwen3.7-max`、`ChatTongyi`、`guard_model_name`、`openai_chat_model_name`、`chunk_count`（响应字段）、`uploaded_at`（响应字段）等过期引用 ✅
- 文档内文件路径、配置键名、API 路径均与当前代码一致 ✅

---

## [2026-08-13] 修复代码审阅问题 3/4/5/6/7/9

### 改动标题
sources 并发竞态改 contextvars；上传跨存储补偿+对账脚本；异步阻塞点 to_thread 化；L3 拒答不落库；删除重排；集中异常处理防泄露

### 问题背景
代码审阅发现的 6 个问题：
1. **P3 sources 并发竞态**：`RagService` 单例用实例属性 `_last_docs` 存 sources，并发请求会互相覆盖。
2. **P4 上传非原子**：向量写入（PGVector 独立同步连接）与 `uploaded_files` 记录（异步 ORM 事务）分属两个事务，`repo.save` 失败会留下孤儿向量。
3. **P5 同步阻塞**：`guard_service.check_question_scope/check` 与 `load_document` 在 async 路径直接同步调用，阻塞事件循环（检索路径已在工具线程池，无需改）。
4. **P6 L3 拒答仍落库**：L3 把越界回答替换为拒答模板后仍写入消息历史，与"越界不入库"原则矛盾。
5. **P7 删除顺序**：`delete_uploaded_file` 先删向量再删记录，记录不存在时也会执行一次向量 DELETE。
6. **P9 错误泄露**：`api/chat.py`、`api/documents.py` 多处 `raise HTTPException(500, f"...{str(e)}")` 把内部异常细节返回客户端。

### 改动文件清单
修改：
- `rag/rag_service.py` — 新增模块级 `_sources_ctx: ContextVar[list[str]]` + `start_sources_collection()`/`collect_sources()`；删除 `self._last_docs`；`rag_summarize()` 改为向 contextvar 收集器追加 sources（去重）；`get_sources()` 改为读 contextvar
- `services/chat_service.py` — `process_message` 重构：L0/L3 走 `asyncio.to_thread`；`create_conversation` 延后到 L3 放行后；L3 拒答返回 `(拒答, [], chat_id)` 不建会话不落库；agent 执行前后用 `start_sources_collection`/`collect_sources` 收集 sources；已有会话才取历史
- `rag/vector_store.py` — 新增 `delete_documents(ids)`（包装 `PGVector.delete`）
- `api/documents.py` — 上传：`VectorStoreService` 实例化一次、`load_document` 走 `asyncio.to_thread`、`repo.save` 失败时补偿删除刚写入向量；删除：重排为先删记录（不存在 404 不动向量）再删向量；移除所有 `except Exception ... str(e)` 分支
- `api/chat.py` — 移除所有 `except Exception ... str(e)` 分支，异常交由全局处理器
- `main.py` — 注册全局 `Exception` 处理器（`logger.exception` 记完整堆栈 + 返回通用文案）与 `RequestValidationError` 处理器（422 友好提示）
- `AGENTS.md` — sources 机制说明改为 contextvar；上传流程补充补偿删除 + 对账脚本
- `README.md` — 会话管理/文档入库/问答流程/文件删除流程同步更新，项目结构加 `scripts/`

新建：
- `scripts/reconcile_embeddings.py` — 孤儿向量清理脚本（默认 dry-run，`--apply` 执行），按 `cmetadata->>'file_id'` 无对应 `uploaded_files` 记录删除

### 关键设计决策与理由
1. **P3 用 contextvars 持可变 list**：contextvars 按 asyncio Task 隔离（FastAPI 每请求一 Task）；工具在 `run_in_executor` 线程里 mutate 的是**同一个 list 对象**，父协程可见。不能用 `.set()` 跨线程回传，故采用"预置容器 + 线程内 mutate"。
2. **P4 补偿删除 + 对账脚本双保险**：跨 DB+向量库无严格 ACID，`repo.save` 失败时按 `added_ids` 补偿删除；commit 时失败（端点已返回）由 `reconcile_embeddings.py` 兜底。
3. **P5 最小改动**：只对 guard 调用与 `load_document` 加 `asyncio.to_thread`。检索路径（`search_with_scores`/`rerank`）已在同步工具内被 LangGraph 用 `run_in_executor` 放进线程池，无需改。
4. **P6 对齐 L0 语义**：L3 拒答不建会话不落库；`agent_history_turns=0` 使"会话延后创建"安全（agent 不需要历史）。
5. **P7 先校验后删除**：`delete_by_id` 先执行，不存在返回 404 不触碰向量；两删同一 async 会话事务内，失败整体回滚。
6. **P9 集中处理**：全局 `Exception` 处理器记录完整堆栈到 `logs/`，对外只返回通用 500 文案；FastAPI 默认已注册 `HTTPException`/`RequestValidationError` 专属处理器，`Exception` 处理器不会拦截 4xx。

### 待办
- `dashscope` 依赖已无 import（ChatTongyi 未使用），可在后续清理移除。
- 对账脚本建议纳入定期运维（cron 每日或上传后执行）。

### 验证结果
- `uv run python -m py_compile` 全部通过 ✅（rag_service/vector_store/chat_service/documents/chat/main/reconcile_embeddings）
- 关键模块导入冒烟测试 OK ✅
- contextvars 单元验证：线程内 mutate 可见 + 并发隔离 ✅
- `process_message` 逻辑测试：L0 越界不建会话不落库 / L3 拒答不建会话不落库 / L3 放行建会话落库+sources 收集 / 已有会话不重建 ✅
- 删除重排测试：记录不存在→404 且不触向量；存在→先删记录后删向量 ✅
- 上传补偿测试：`repo.save` 失败→`delete_documents` 被调用 ✅
- `reconcile_embeddings.py` dry-run：连接成功，孤儿数 0 ✅
- 全局异常处理器（TestClient）：500 返回通用文案且不含异常细节、422 友好提示、404 不受影响 ✅

---

## [2026-08-13] Query 改写模块封装为 RewriteAgent（create_agent）

### 改动标题
`QueryRewriter`（prompt+LLM 链）迁移为 `agent/rewrite_agent.py` 的 `RewriteAgent`（`create_agent` 封装，与 ReactAgent 同构），模型改用本地 `ChatOllama`

### 问题背景
原 `rag/query_rewriter.py` 的 `QueryRewriter` 只是 `PromptTemplate | OllamaLLM | StrOutputParser` 简单链，与其他 agent（ReactAgent/GuardService 均单例）架构不统一；`OllamaLLM` 是 `BaseLLM`，无法用 `create_agent` 封装。需要把它升级为真正的 agent 组件。

### 改动文件清单
新建：
- `agent/rewrite_agent.py` — `RewriteAgent` + `@lru_cache get_rewrite_agent()` 进程级单例；`create_agent(model=get_ollama_chat_model(), system_prompt=load_query_rewrite_prompt(), tools=[], middleware=[log_before_model])`；`rewrite(query)` 同步 `invoke`，异常降级返回原 query

修改：
- `rag/model/factory.py` — 新增 `get_ollama_chat_model()`（`ChatOllama`，`qwen3.5:4b`，`reasoning=False`）
- `rag/rag_service.py` — `from rag.query_rewriter import QueryRewriter` → `from agent.rewrite_agent import get_rewrite_agent`；`self._rewriter = get_rewrite_agent()`
- `prompts/query_rewrite_prompt.txt` — 删除 `{query}` 模板占位（query 改由 user 消息传入），改为纯 system prompt
- `AGENTS.md` — 模型接线更新（Guard 走 `get_ollama_llm`、Rewrite 走 `get_ollama_chat_model`，注明 create_agent 需 BaseChatModel）
- `README.md` — 项目结构加 `agent/rewrite_agent.py`；模型表 Query Rewrite 行注明 ChatOllama

删除：
- `rag/query_rewriter.py`（内容迁至 `agent/rewrite_agent.py`，无其他引用）

### 关键设计决策与理由
1. **放 `agent/` 包**：与 `react_agent.py` 同级，符合"agent 组件归 agent 包"的架构；`rag.rag_service → agent.rewrite_agent →（rag.model.factory、agent.tool.middleware）`，无循环导入（`agent.tool.agent_tools` 对 `rag.rag_service` 是函数内惰性导入）。
2. **用 `ChatOllama` 而非 `OllamaLLM`**：`create_agent` 只接受 `BaseChatModel`（已核 `langchain/agents/factory.py` 签名）；`OllamaLLM` 保留给 guard_service。`reasoning=False` 关闭 qwen3.5:4b 思考模式避免超时。
3. **不挂工具**：改写是单轮无工具变换，`tools=[]`，避免与 `rag_summarize` 形成递归依赖；中间件只用同步 `log_before_model`（`monitor_tool` 为异步且仅工具调用触发）。
4. **同步 `invoke`**：`rag_summarize` 是同步工具（线程池执行），改写 agent 用同步 `invoke` 无需 async 化，不阻塞事件循环。

### 待办
- 无。

### 验证结果
- `py_compile` 通过 ✅（factory/rewrite_agent/rag_service）
- 导入冒烟：`agent.rewrite_agent`、`rag.rag_service`、`agent.react_agent`、`services.chat_service` 全部 import OK，无循环导入 ✅
- 端到端（本地 Ollama 运行）：`RewriteAgent().rewrite("天气比较热，适合穿什么材质的衣服？")` → 返回关键词（`log_before_model` 中间件生效）✅
- 降级路径（Ollama 不可达）：`rewrite` 捕获异常返回原 query，WARNING 日志正常 ✅

---

## [2026-08-13] L1 检索封装为 RetrievalAgent（create_agent）

### 改动标题
`RagService.retriever_docs` 确定性检索管道（向量召回→Rerank→阈值过滤）重构为 `agent/retrieval_agent.py` 的 `RetrievalAgent`（`create_agent`，工具 `vector_search` + `rerank`，模型 DeepSeek）

### 问题背景
此前"查询向量库"逻辑在 `RagService.retriever_docs`（+ 装配 `VectorStoreService`/`RerankClient`/`_TTLCache`）中，是确定性管道但非 agent 组件。与 RewriteAgent/ReactAgent 的"单例 + 清晰接口"架构不统一；用户要求把检索也封装成 create_agent 智能体。

### 改动文件清单
新建：
- `agent/retrieval_agent.py` — `RetrievalAgent` + `@lru_cache get_retrieval_agent()` 单例；`create_agent(model=get_chat_model(), system_prompt=load_retrieval_prompt(), tools=[vector_search, rerank], middleware=[log_before_model])`；`retrieve(query)` 同步 invoke，文档经 `_retrieved_docs_ctx` contextvar 回传，agent 失败/无产出时降级为向量 top_n
- `prompts/retrieval_prompt.txt` — 检索 agent system prompt（先 vector_search 再 rerank，完成回复"检索完成"）

修改：
- `rag/rag_service.py` — 删除 `retriever_docs`、`_TTLCache`、`VectorStoreService`/`get_reranker` 装配、死方法 `get_sources()`；`rag_summarize` 改为 `get_retrieval_agent().retrieve(query)`（sources 收集 + 格式化 + 拒答逻辑不变）
- `config/prompts.yml` — 加 `retrieval_prompt_path`
- `utils/prompt_loader.py` — 加 `load_retrieval_prompt()`
- `AGENTS.md` — 架构与模型接线更新（RetrievalAgent 位置、模型、contextvar 回传、monitor_tool 同步限制）
- `README.md` — 项目结构加 `agent/retrieval_agent.py`、模型表加"检索 Agent（L1）"行、数据流 L1 描述更新

### 关键设计决策与理由
1. **真 create_agent + 双工具**：`vector_search`（宽松召回 candidate_k）→ `rerank`（精排 + rerank_score_min 过滤），LLM 只驱动工具调用顺序。
2. **文档经 contextvar 回传**：LLM 只输出文本、拿不回 `Document` 对象，故 `_retrieved_docs_ctx` 持可变 list，工具在同步 invoke 同线程 mutate，`retrieve()` 读取（与 sources contextvar 同模式）。
3. **只挂同步中间件**：同步 `.invoke()` 下异步 `monitor_tool` 无法工作（已核 `tool_node.py:1033`），仅挂 `log_before_model`，工具内 `logger.info` 记录调用。
4. **降级兜底**：agent 抛异常或未产出文档时，`retrieve()` 退化为 `search_with_scores` top_n（不 rerank），对应旧 rerank 失败降级语义，保证可用性。
5. **rerank 越界防护**：对 `r["index"]` 增加类型与边界校验，避免越界 IndexError 污染 agent 调用。
6. **模型复用 `get_chat_model()`（DeepSeek）**：工具调用可靠性优于本地 4B 模型；因不依赖模型文本输出，`max_tokens=512` 足够。

### 待办
- 建议部署后跑一轮真实检索对比：agent 检索结果 vs 旧确定性管道是否一致（语义等价性）。

### 验证结果
- `py_compile` 通过 ✅（retrieval_agent/rag_service/prompt_loader）
- 导入冒烟：`agent.retrieval_agent`、`rag.rag_service`、`agent.react_agent`、`services.chat_service`、`main` 全部 import OK，无循环导入 ✅
- `retrieve()` 逻辑测试（mock vector_store/reranker/agent）✅：
  - 正常：agent 依次调 vector_search→rerank，文档经 contextvar 正确回传 ✅
  - agent 抛异常 → 降级向量 top_n ✅
  - 只调 vector_search 未 rerank → 返回候选 ✅
  - 空候选 → 返回空不抛异常 ✅
  - TTL 缓存命中不再调用 agent ✅
  - rerank 返回越界 index 被过滤 ✅

---

## [2026-08-13] README 复核与同步（对齐 RetrievalAgent 落地后现状）

### 改动标题
重新通读项目后更新 README：防乱说话层级改为四层（L0-L3）、补检索 Agent/改写/检索 prompt 相关描述、修正删除流程顺序

### 改动文件清单
修改：
- `README.md` — 文档同步

### 关键改动
1. **"三层"→"四层"防乱说话**：README 表格与架构图实际展示 L0/L1/L2/L3 四层，标题/目录/概览统一改为"四层防乱说话架构"。
2. **补 RetrievalAgent 相关**：架构图 L1 标注 `← RetrievalAgent (DeepSeek)`；技术栈 DeepSeek 行补充"检索 Agent"；`DEEPSEEK_API_KEY` 环境变量说明补充 RetrievalAgent；`rag.yml` 的 `chat_model_name` 注明同时供主/检索 Agent 使用；prompts.yml 配置列表补 `retrieval_prompt_path`；项目结构 prompts 目录补 `query_rewrite_prompt.txt`/`retrieval_prompt.txt`，`rag_summarize.txt` 标注为保留备用。
3. **修正描述**：项目结构 `rag_service.py` 从"检索 + Rerank + TTL 缓存"改为"RAG 编排（改写 → 检索 → sources → 格式化）"；接口说明"删除文件"的先后顺序改为"先删记录（不存在 404）再删向量"（对齐问题 7 修复）；`/api/chat/` 越界说明补充 L3 同样不入库。
4. **多轮上下文说明**：知识库问答特性明确 `agent_history_turns=0`（默认每轮独立、不传历史给 Agent），可配置开启。

### 验证结果
- grep 校验：README 不再残留"三层"、旧删除顺序、`rag_service 检索+Rerank+TTL` 等过期表述 ✅
- 架构图 L1 标注与框宽保持对齐 ✅

---
