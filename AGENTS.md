# AGENTS.md

为 OpenCode 会话编写的 `FastAPI_chunking` 仓库专属指南（RAG 问答后端：FastAPI + LangChain + PGVector）。阅读前请以源码为准——README 若与代码不一致，以代码为准并及时修正 README。

## 工具链与命令

- 包管理器为 **`uv`**（根目录有 `uv.lock`）。Python **>= 3.13**。
- 启动应用：`uv run uvicorn main:app --reload`（ASGI 入口为 `main:app`）。
- **没有 lint / typecheck / CI 配置。** 当前已加入 pytest 测试，但没有 pre-commit、ruff、mypy 或 CI 配置。
- 健全性检查：对改动 Python 文件运行 `uv run python -m py_compile`，并使用 `uv run pytest tests -q`（或当前环境等价的 pytest 命令）运行测试。
- 不要编造 `npm run lint` 之类的命令；需要验证时，对改动文件跑 `py_compile`，或启动服务访问 `/docs`。

## 环境与配置（容易踩坑）

- 数据库凭据位于仓库根目录的 **`.env`**（已被 gitignore）。键由 `core/config.py:EnvConfig` 通过 pydantic-settings 读取，**大小写不敏感**且带别名：`HOST`/`DB_HOST`/`host`、`PORT`、`USER`/`DB_USER`、`PASSWORD`/`DB_PASSWORD`、`DB`/`DB_NAME`/`database`/`dbname` 均可。
- `API_KEYS` 为逗号分隔的 API 鉴权密钥，可放 `.env` 或系统环境变量；未配置时 `core/security.py:require_api_key` 直接放行，配置后所有 `/api/*` 接口校验 `X-API-Key` 请求头，缺失/错误返回 401。
- `SILICONFLOW_API_KEY` 必须是**真实的操作系统环境变量**，不能放 `.env`。它在 `rag/model/factory.py` 中通过 `os.environ.get` 读取，用于默认嵌入模型（SiliconFlow）。
- `core/config.py` 以**懒加载 YAML 字典**（`_LazyConfig`）形式暴露 `pg_conf`、`rag_conf`、`prompts_conf`、`db_conf`。仅 `import core.config` 不会读 YAML——首次按键访问才加载。注意：`rag/vector_store.py` 在类定义阶段就读取 `pg_conf["chunk_size"]`，因此 import 该模块会触发 YAML 加载。`config/` 是非敏感参数的事实来源。
- `core/paths.py` 从 `__file__` 向上查找名为 **`config`** 的目录来定位项目根。不要重命名 `config/` 或移走其中文件，否则配置加载会坏。

## 一个应用里有两套数据库驱动

- 异步 ORM 路径（`db/engine.py`，所有 `db/*_repo.py`）：`postgresql+asyncpg://`，SQLAlchemy async。
- 向量路径（`rag/vector_store.py`，`langchain_postgres.PGVector`）：`postgresql+psycopg://`（同步）。
- 两者都基于同一份 `.env` 凭据。`asyncpg` 和 `psycopg` 都是必需依赖，不要删除任何一个。

## Schema 与 DDL 陷阱

- **ORM 表不会自动创建。** 代码中没有任何 `Base.metadata.create_all`。必须手动创建 `conversations`、`messages`、`uploaded_files`（数据库用户需有 DDL 权限）。只有 `langchain_pg_embedding` 和 `langchain_pg_collection` 由 `PGVector` 自行创建。
- **跨表 UUID 格式不一致：** 应用表存储带连字符的 UUID；`langchain_pg_embedding.cmetadata->>'file_id'` 存储**不带连字符**的 UUID。关联时需用 `REPLACE(uf.id::TEXT, '-', '') = (lpe.cmetadata->>'file_id')`。`scripts/data_test.sql` 有标准查询和 `TRUNCATE ... CASCADE` 重置脚本。
- 必须先启用 PGVector 扩展：`CREATE EXTENSION IF NOT EXISTS vector;`。

## 架构与约定

- 分层：**`api/`（仅 HTTP）→ `services/`（业务编排）→ `db/*_repo.py`（数据访问）**。新端点放 `api/`，业务逻辑放 `services/`，schema 放 `schemas/`。
- 鉴权：`api/chat.py` 与 `api/documents.py` 的 router 统一挂载 `core/security.py:require_api_key` 依赖，`API_KEYS` 留空时向后兼容放行。
- 会话记忆：一个 `chatId` 可包含多个主题，`conversation_topics` 同时只保留一个 active 主题；主题切换归档旧主题，当前 Agent 只读取 active topic 的摘要、最近有效轮次和已确认长期偏好。
- 上下文过滤：消息使用 `turn_id` 配对 Human/AI 轮次，只有 `memory_eligible=true`、非拒答、非 OUT 范围消息可进入上下文；不得把完整历史、其他主题原始消息或工具参数传给 Agent。
- 摘要降级：`SummaryService` 使用本地 Ollama 更新摘要；摘要失败保留旧摘要，不影响主回答，并由 `summary_version` 乐观并发控制避免旧摘要覆盖新摘要。
- 长期记忆：`MemoryService` 使用本地 Ollama，仅保存用户明确表达且置信度达到阈值的服装偏好；`anonymous` 用户不写入，过期记忆不注入，可通过 `/api/memory` 接口删除。
- **事务边界（硬性规则）：** Repository 不得调用 `session.commit()`。`db/session.py:get_db` 在请求结束时提交，任何异常都会回滚。Service 层多步写入只需顺序调用各 repo 方法——任一抛异常即整体回滚。不要添加 repo 内的 commit。
- `ReactAgent` 是**进程级单例**，通过 `services/chat_service.py:_get_react_agent` 的 `lru_cache(maxsize=1)` 实现。状态跨请求共享——往里加每请求状态要小心。
- L1 检索走 `agent/retrieval_agent.py` 的 `RetrievalAgent`（`create_agent` 单例，`get_retrieval_agent()`），工具为 `vector_search`（宽松召回）→ `rerank`（精排过滤），模型用 DeepSeek `get_chat_model()`。**LLM 只驱动工具调用，最终 `list[Document]` 经 `_retrieved_docs_ctx` contextvar 回传**（同步 `invoke` 下工具与 `retrieve` 同线程）；agent 调用失败/无产出时 `retrieve()` 退化为向量 top_n。
- Chat 的 `sources` 由 `rag_summarize` 工具在检索时写入**请求级 `contextvars` 容器**（`rag/rag_service.py` 的 `_sources_ctx`），`chat_service.process_message` 在 agent 执行后读取。**不要用实例属性/全局变量保存 sources**（`RagService` 是进程级单例，并发会互相覆盖），也不要再检索一遍来填 `sources`。
- 上传流程：流式写入 `data/`，边写边算 MD5，**按 MD5 拒绝重复入库**。`data/` 已 gitignore。向量写入与 `uploaded_files` 记录分属两个事务——`repo.save` 失败时会补偿删除刚写入的向量；存量孤儿用 `uv run python scripts/reconcile_embeddings.py --apply` 清理。
- 静态前端：根路径 `/` 返回 `static/index.html`；`/static` 仅在该目录存在时挂载。`lifespan` 在关闭时释放异步引擎。
- 前端主题状态通过 DOM 节点和 `textContent` 渲染；动态文件名、用户消息和 AI 回答不得使用 `innerHTML`、`insertAdjacentHTML` 或内联事件处理器，避免存储型 XSS。

## 模型接线

- 默认聊天模型：**DeepSeek** `deepseek-v4-flash`，经 `get_chat_model()`（`ChatOpenAI`，`base_url=https://api.deepseek.com`，`DEEPSEEK_API_KEY`），用于 ReactAgent 与 RetrievalAgent。
- 默认嵌入：**SiliconFlow** `BAAI/bge-m3`，经 `get_embed_model()`（`OpenAIEmbeddings`，`SILICONFLOW_API_KEY`）——`rag/vector_store.py` 实际使用的就是它。
- L0/L3 Guard 走本地 Ollama `get_ollama_llm()`（`OllamaLLM`，`qwen3.5:4b`，`http://localhost:11434`），用于 `services/guard_service.py`。
- Query Rewrite 封装为 `agent/rewrite_agent.py` 的 `RewriteAgent`（`create_agent` 进程级单例，`get_rewrite_agent()`），模型用 `get_ollama_chat_model()`（`ChatOllama`，`qwen3.5:4b`）。
- L1 检索封装为 `agent/retrieval_agent.py` 的 `RetrievalAgent`（`create_agent` 进程级单例，`get_retrieval_agent()`），模型用 `get_chat_model()`（DeepSeek），工具 `vector_search` + `rerank`。
- 注意 `create_agent` 只接受 `BaseChatModel`，故不能用 `OllamaLLM`（那是 `BaseLLM`）；同步 `invoke` 下异步 `monitor_tool` 中间件无法工作，RewriteAgent/RetrievalAgent 只挂同步 `log_before_model`。
- 需本地启动 `ollama serve`；未启动时 L0/L3 静默放行（解析失败默认 IN）、Query Rewrite 回退原始 query。
- 主题路由、滚动摘要和长期记忆提取同样使用本地 Ollama；对应模块失败时必须走受限降级，不得恢复为完整历史上下文。
- 切换模型需同时改 `config/rag.yml` 和 `rag/model/factory.py`。
- 实际使用的文本切分器是 `langchain_text_splitters.RecursiveCharacterTextSplitter`。

## 进度日志（changelog.md）

- 仓库根目录 `changelog.md` 是 AI 跨会话进度日志，用于解决上下文超限问题。
- **每完成一个大功能后，AI 必须总结"做了什么改动"并追加一条记录到 `changelog.md`**（追加，不覆盖；按既有格式写：日期、标题、文件清单、关键决策、待办、验证结果）。
- 开新会话时，用户说"请先阅读 changelog.md 了解当前进度"，AI 应先读此文件再开工。
- `changelog.md` 纳入版本管理（不在 `.gitignore`）。

## 文档同步（README）

- **每次修改更新代码、配置或依赖后，AI 必须同步检查并更新 `README.md`**，使其与实际实现保持一致（接口响应字段、配置键、模型接线、目录结构、数据流等）。
- 以源码为准：README 与代码不一致时，修正 README 而非反过来。
- 与 changelog 记录并行执行：改动完成后同时更新 changelog.md 与 README.md（仅改内部算法、不改外部可见行为的，可在 changelog 注明"无需更新 README"）。
