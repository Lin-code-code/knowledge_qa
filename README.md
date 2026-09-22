# 服装垂直客服 RAG 问答系统

基于 **Python + FastAPI + LangChain + PGVector** 的服装行业智能问答系统，带四层安全防乱说话架构（L0 预检 + L1/L2/L3）。

---

## 目录

- [项目概览](#项目概览)
- [功能特性](#功能特性)
- [企业级会话记忆](#企业级会话记忆)
- [四层防乱说话架构](#四层防乱说话架构)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [运行要求](#运行要求)
- [配置说明](#配置说明)
- [安装与启动](#安装与启动)
- [接口说明](#接口说明)
- [数据流与工作原理](#数据流与工作原理)
- [常见问题](#常见问题)

---

## 项目概览

`FastAPI_chunking` 是一套服装行业垂直客服系统，支持上传知识文件、向量检索、多轮问答，并内置四层安全机制防止大模型胡说八道：

1. 用户上传服装知识文件（尺码表、洗护说明、面料介绍等）
2. 系统读取文件并按配置切分文本，写入 PGVector
3. 用户提问时，先经 L0 域内预检判定是否属于服装领域
4. 越界问题直接拒答（不入库、不调 Agent）
5. 主题路由判断继续当前主题、新建主题、混合问题、澄清或拒答
6. 当前主题摘要、最近有效轮次和用户明确偏好组成受限上下文
7. 域内问题经向量检索 + Rerank 精排后交给 Agent 生成回答
8. 回答经 L3 分类器兜底，越界输出替换为统一拒答话术

---

## 功能特性

### 四层防乱说话

| 层级 | 名称 | 位置 | 作用 |
|------|------|------|------|
| L0  | 域内预检 | Agent 执行前 | 代码级拦截越界问题，不入库不调 Agent |
| L1  | 检索阈值+Rerank | 检索阶段 | 向量宽松召回 → Rerank 精排 → score 阈值过滤 |
| L2  | Prompt 约束 | Agent prompt | 领域边界 + 越界清单 + few-shot 示例 |
| L3  | 兜底分类器 | Agent 执行后 | 独立模型检查回答合规性，越界替换拒答模板 |

### 文档上传与入库

- 支持上传知识文件（默认 `txt`、`pdf`）
- 上传后先保存到 `data/` 目录
- 使用 `RecursiveCharacterTextSplitter` 自动切分
- 切分结果写入 PGVector
- 使用 MD5 记录做去重，避免重复入库
- 前端文件列表展示文件名、大小、片段数

### 知识库问答

- 基于向量检索 + Rerank 精排召回相关内容
- 支持基于 ReactAgent 代理模式进行意图识别和工具调用
- 使用提示词模板组织回答（RAG 原文返回，Agent 自行分析匹配）
- 消息历史会落库，但 Agent 不再接收完整历史；上下文只包含当前 active topic 的摘要、最近有效问答对和按当前问题/意图筛选后的长期偏好
- 检索结果带缓存（可配置 TTL 与容量上限）
- 支持返回会话 ID，便于前端继续追问

### 会话管理

- 一个 `chatId` 可以包含多个主题，系统自动维护一个 active topic，主题切换时归档旧主题
- 拒答、越界消息可以作为审计记录保存，但 `memory_eligible=false`，不会进入后续上下文
- 澄清问题不执行检索和主 Agent；当前轮标记为不可用于记忆
- 创建会话、获取会话列表
- 获取某个会话的消息列表
- 获取主题列表、主题详情和归档主题
- 管理用户明确表达的长期服装偏好；偏好按当前问题意图筛选后注入，尺码、颜色、面料、穿着限制四类互不串用
- 删除会话及其消息

### 前端入口

- 根路径 `/` 返回 `static/index.html`
- `/static` 挂载静态资源目录

---

## 企业级会话记忆

系统把“完整会话”和“生成上下文”分开管理：

```text
当前用户消息
    -> TopicRouter（主题/意图/范围判断）
    -> CONTINUE / NEW_TOPIC / MIXED / CLARIFY / OUT_OF_SCOPE
    -> 当前主题摘要 + 最近有效轮次 + 用户明确偏好
    -> 当前问题检索
    -> ReactAgent 回答与 L3 安全检查
    -> 保存消息、滚动更新主题摘要、提取长期偏好
```

- `chatId` 表示完整会话，`topicId` 表示会话内主题。
- `conversation_topics` 保存主题标签、摘要、意图、范围和摘要版本；同一会话同时只有一个 active 主题。
- `messages` 增加 `topic_id`、`turn_id`、`intent`、`scope_label`、`is_refusal`、`memory_eligible`，兼容原有消息字段。
- `memory_items` 只保存用户明确表达的尺码、颜色、面料和穿着限制；`anonymous` 用户不写长期记忆。
- `conversation_memory_enabled=false` 时保留基础问答和消息落库，但不读取或创建主题、不更新摘要，也不写入长期记忆。
- 其他主题原始消息、拒答消息、越界内容、工具参数和未确认推断不会进入当前 Agent Prompt。
- 摘要失败只保留旧摘要，不影响当前回答；摘要更新使用 `summary_version` 做乐观并发控制。

### 主题路由行为

| 动作 | 行为 |
|------|------|
| `CONTINUE` | 复用 active topic，用 `canonical_query` 检索 |
| `NEW_TOPIC` | 归档旧主题，创建新 active topic，隔离旧主题原始消息 |
| `MIXED` | 只检索服装子问题，对越界子问题使用拒答模板 |
| `CLARIFY` | 直接返回澄清问题，不检索、不调用主 Agent |
| `OUT_OF_SCOPE` | 返回统一拒答；新会话不创建，已有会话仅写不可用审计记录 |

### 数据库迁移

ORM 不会自动创建会话相关表。先备份 `conversations`、`messages`，确认数据库支持 `gen_random_uuid()`，再执行幂等迁移：

```powershell
psql -h <host> -U <user> -d <dbname> -f scripts/migrate_conversation_memory.sql
```

迁移会启用 `pgcrypto`，创建 `conversation_topics`、`memory_items`，扩展 `messages`，为存量会话建立默认主题并按时间生成 `turn_id`；包含拒答模板的旧消息会被标记为不可进入上下文。

---

## 四层防乱说话架构

```text
用户提问
    |
    v
+--------------------------------------+
|  L0 域内预检 (GuardAgent)                |   ← 本地 Ollama qwen3.5:4b
|  YES/NO 分类                           |       解析失败默认放行
|  越界 → 直接返回拒答，不入库                     |
+-------------------+------------------+
                    | 域内
                    |
    v
+--------------------------------------+
|  L1 检索 + Rerank                      |  ← RetrievalAgent (DeepSeek)
|  candidate_k → Rerank 精排             |      LLM 只驱动工具调用
|  rerank_score >= 0.05 过滤             |
+-------------------+------------------+
                    | 检索结果
                    |
    v
+--------------------------------------+
|  L2 ReactAgent (deepseek-v4-flash)   |  ← DeepSeek
|  Prompt 约束领域边界 + 越界清单                |      含 4 条 few-shot 示例
|  工具: rag_summarize                   |
+-------------------+------------------+
                    | Agent 回答
                    |
    v
+--------------------------------------+
|  L3 分类器 (GuardAgent)                  |   ← 本地 Ollama qwen3.5:4b
|  IN/OUT/REFUSE 三分类                   |       解析失败默认放行
|  越界 (OUT) → 替换拒答模板                   |
+-------------------+------------------+
                    | 最终回答
                    |
    v
        用户
```

---

## 技术栈

- **Python** >= 3.13
- **FastAPI**：API 服务
- **Uvicorn**：ASGI 服务器
- **SQLAlchemy** + **asyncpg**：异步数据库访问
- **PostgreSQL + PGVector**：向量存储
- **LangChain & LangGraph**：Agent 编排与大模型调度
- **LangChain Community / LangChain PGVector**：模型与向量相关能力
- **DeepSeek**：主聊天模型 + 检索 Agent（ReactAgent / RetrievalAgent）
- **SiliconFlow**：嵌入模型 + Rerank 模型
- **Ollama**：本地 L0/L3 Guard 分类模型 + Query Rewrite 改写模型
- **PyYAML**：YAML 配置加载
- **PyPDF**：PDF 解析
- **httpx**：Rerank HTTP 客户端

---

## 项目结构

```text
FastAPI_chunking/
├─ main.py                     # FastAPI 应用入口
├─ pyproject.toml              # 项目依赖与构建配置
├─ uv.lock                     # uv 锁定文件
│
├─ core/                       # 基础设施
│  ├─ config.py                # EnvConfig + 懒加载 YAML 配置
│  ├─ logger.py                # 日志封装（控制台 + 按天轮转文件）
│  ├─ paths.py                 # 路径工具（项目根目录发现）
│  ├─ security.py              # API Key 鉴权依赖
│  └─ validators.py            # 通用校验函数（文件扩展名等）
│
├─ domain/                     # 领域层（纯 Python，无框架依赖）
│  ├─ entities.py              # 领域实体（Conversation / Message / ConversationTopic / MemoryItem / UploadedFile / FileSummary）
│  ├─ decisions.py             # 决策对象（TopicDecision / TopicSegment / ChatAnswer / MemoryCandidate）
│  ├─ enums.py                 # Role / ScopeLabel / TopicAction / TopicStatus
│  ├─ errors.py                # 会话、主题、记忆、文档领域异常
│  └─ ports.py                 # 端口契约（typing.Protocol：仓储端口 + AI/检索端口）
│
├─ db/                         # 数据访问层（实现 domain 的 Repository 端口）
│  ├─ engine.py                # 异步数据库引擎与 session 工厂
│  ├─ session.py               # get_db() / close_db()：持有事务边界（请求结束提交，异常回滚）
│  ├─ mappers.py               # ORM 模型 ↔ 领域实体映射
│  ├─ models/                  # SQLAlchemy ORM 模型（仅 db 内部使用）
│  │  ├─ base.py               # DeclarativeBase
│  │  ├─ conversation.py       # Conversation + Message + ConversationTopic
│  │  ├─ memory_item.py        # MemoryItem
│  │  └─ uploaded_file.py      # UploadedFile
│  └─ repositories/            # Repository 端口实现（均不 commit）
│     ├─ conversation.py       # 会话、主题与消息仓储
│     ├─ topic.py              # 主题切换、摘要乐观更新
│     ├─ memory.py             # 长期记忆查询、覆盖与删除
│     └─ file.py               # FileRepository（文件记录 CRUD + 向量删除）
│
├─ services/                   # 业务编排层（只编排用例，不导入 api/db/agent/rag 与 Web 框架）
│  ├─ chat_service.py          # ChatService：主题路由 + L0 预检 + Agent + L3 兜底
│  ├─ conversation_service.py  # 会话创建、列表、消息查询与删除
│  ├─ topic_service.py         # 主题列表、详情与归档
│  ├─ document_service.py      # 文件上传、列表与删除用例
│  ├─ context_builder.py       # 主题隔离、轮次配对和 token 裁剪
│  └─ memory_service.py        # 长期偏好提取与保存
│
├─ api/                        # API 层（只处理 HTTP：参数绑定、状态码与响应体）
│  ├─ chat.py                  # 问答与会话接口
│  ├─ documents.py             # 文件上传/列表/删除接口
│  └─ dependencies.py          # 组合根：组装 Repository + Service + 端口适配器
│
├─ agent/                      # AI 能力适配器（实现 domain 的 ChatAgent/Guard/Router/Summary/Memory 端口）
│  ├─ chat_agent.py            # ChatAgent：Query Rewrite + 检索 + 请求级 sources 收集
│  ├─ guard_agent.py           # GuardAgent：L0 域内预检 + L3 输出分类器
│  ├─ topic_router.py          # TopicRouter：主题/意图/范围路由
│  ├─ summary_agent.py         # SummaryAgent：主题滚动摘要
│  ├─ memory_agent.py          # MemoryExtractor：长期偏好提取
│  ├─ react_agent.py           # ReactAgent（LangGraph 实现）
│  ├─ rewrite_agent.py         # RewriteAgent（query 改写，create_agent 封装）
│  ├─ retrieval_agent.py       # RetrievalAgent（向量检索+Rerank，create_agent 封装）
│  └─ tool/
│     ├─ agent_tools.py        # Agent 工具（rag_summarize, 时间查询）
│     └─ middleware.py         # 工具调用监控与日志
│
├─ rag/                        # RAG 检索与模型工厂
│  ├─ rag_service.py           # RAG 编排（改写 → 检索 → sources → 格式化）
│  ├─ vector_store.py          # PGVector 文档入库与向量检索
│  └─ model/
│     ├─ factory.py            # 模型工厂（聊天 / 嵌入 / Rerank / Ollama）
│     └─ reranker.py           # SiliconFlow /v1/rerank HTTP 客户端
│
├─ config/                     # YAML 配置（已纳入版本管理）
│  ├─ pgvector.yml             # 切分、文件类型、集合名、检索候选数
│  ├─ rag.yml                  # 模型名称 + Rerank/Guard 配置 + 缓存
│  ├─ prompts.yml              # 所有提示词文件路径
│  └─ database.yml             # 连接池与对话管理参数
│
├─ utils/                      # 工具函数
│  ├─ file_handler.py          # 文档读取（pdf_loader / txt_loader）
│  └─ prompt_loader.py         # 提示词模板文件加载（含 guard/scope）
│
├─ schemas/
│  ├─ chat.py                  # Pydantic 请求/响应模型
│  ├─ topic.py                 # 主题路由和主题 API 模型
│  └─ memory.py                # 长期记忆 API 模型
│
├─ prompts/                    # 提示词模板
│  ├─ main_prompt.txt          # Agent 系统提示词（服装垂直客服）
│  ├─ scope_check_prompt.txt   # L0 域内预检 prompt
│  ├─ guard_prompt.txt         # L3 分类器 prompt
│  ├─ query_rewrite_prompt.txt # 检索词改写 prompt
│  ├─ retrieval_prompt.txt     # 检索 Agent prompt
│  ├─ topic_router_prompt.txt  # 主题路由 prompt
│  ├─ summary_prompt.txt       # 主题摘要 prompt
│  ├─ memory_extract_prompt.txt# 长期偏好提取 prompt
│  ├─ refusal_template.txt     # 统一拒答话术
│  └─ rag_summarize.txt        # 历史遗留（rag_summarize 不再调 LLM，保留备用）
│
├─ static/                     # 前端静态文件
│  ├─ index.html               # SPA 入口
│  ├─ css/
│  └─ js/
│
├─ scripts/                     # 运维脚本
│  ├─ create_hnsw_index.py      # 为 langchain_pg_embedding 创建 HNSW 索引
│  ├─ migrate_conversation_memory.sql # 会话记忆幂等迁移
│  └─ reconcile_embeddings.py   # 清理孤儿向量（上传失败兜底，--apply 执行删除）
│
├─ data/                       # 上传文件临时目录
├─ logs/                       # 运行日志（按天轮转，保留 30 天）
└─ tests/                      # pytest 测试（鉴权、接口错误语义、连接串编码、架构边界）
```

### 分层与依赖规则

| 层 | 职责 | 依赖约束 |
|------|------|---------|
| `api/` | **只处理 HTTP**：参数绑定、鉴权、领域异常 → 状态码与响应体 | 只通过 `api/dependencies.py`（组合根）取用应用服务，不直接导入 Repository 或 ORM |
| `services/` | **只编排用例**：业务流程与事务内多步调用 | 依赖 `domain` 端口（`typing.Protocol`）与 `core`，不导入 `api`/`db`/`agent`/`rag`/FastAPI/SQLAlchemy |
| `domain/` | 领域实体、决策对象、枚举、异常与端口契约 | **无框架依赖**，只用标准库 |
| `db/` | **实现 Repository 端口**：ORM 模型 + 仓储实现 + 映射 | 仓储返回领域实体，不 `commit()`（事务边界由 `db/session.py:get_db` 持有） |
| `agent/`、`rag/` | 实现 AI/检索端口（Guard、Router、Summary、Memory、ChatAgent、向量库） | 由组合根注入 Service，Service 不直接导入 |

- `api/dependencies.py` 是唯一的**组合根**：把 `db` 仓储、`agent`/`rag` 适配器组装成 Service。
- 本次分层重构**未改变外部 HTTP 接口（路径、方法、请求/响应字段、状态码与中文文案）、数据库表结构和配置键**。

---

## 运行要求

### 基础环境

- Python 3.13+
- PostgreSQL 数据库（需手动启用 PGVector 扩展）
- 可访问的模型服务（DeepSeek / SiliconFlow / 本地 Ollama）

### 数据库准备

```powershell
psql -h <host> -U <user> -d <dbname> -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

> **注意**：ORM 表（`conversations`、`messages`、`uploaded_files`）不会自动创建，需手动执行 DDL 或使用 `scripts/data_test.sql`。`langchain_pg_embedding` 和 `langchain_pg_collection` 由 PGVector 自行创建。

### 模型依赖

| 用途 | 模型 | 服务商 | 接入方式 |
|------|------|--------|---------|
| 主 Agent（L2） | `deepseek-v4-flash` | DeepSeek | `DEEPSEEK_API_KEY`（系统环境变量） |
| 检索 Agent（L1） | `deepseek-v4-flash` | DeepSeek | 复用 `DEEPSEEK_API_KEY` |
| 嵌入 | `BAAI/bge-m3` | SiliconFlow | `SILICONFLOW_API_KEY`（系统环境变量） |
| Rerank | `BAAI/bge-reranker-v2-m3` | SiliconFlow | 复用 `SILICONFLOW_API_KEY` |
| L0/L3 Guard | `qwen3.5:4b` | Ollama（本地） | 需本地启动 Ollama（`localhost:11434`） |
| Query Rewrite | `qwen3.5:4b`（ChatOllama） | Ollama（本地） | 复用上述 Ollama 服务 |

> **注意**：L0 域内预检、L3 兜底分类器与 Query Rewrite 均依赖本地 Ollama 服务。若 Ollama 未启动：L0/L3 会静默放行（解析失败默认 IN），越界拦截失效；Query Rewrite 会回退为原始 query。请确保部署环境已启动 `ollama serve` 并拉取 `qwen3.5:4b`。

---

## 配置说明

### 1. `.env` 文件（数据库凭据，已 .gitignore）

```
HOST=192.168.1.100
PORT=5432
USER=postgres
PASSWORD=your_password
DB=vectordb
```

字段别名（大小写不敏感）：`HOST`/`DB_HOST`/`host`、`PORT`、`USER`/`DB_USER`、`PASSWORD`/`DB_PASSWORD`、`DB`/`DB_NAME`/`database`/`dbname`。

### 2. 系统环境变量

- `SILICONFLOW_API_KEY`：用于嵌入、Rerank 模型（**不能放 `.env`**）
- `DEEPSEEK_API_KEY`：用于主聊天模型（ReactAgent）与检索 Agent（RetrievalAgent）
- `API_KEYS`：API 鉴权密钥，逗号分隔多个 key（可放 `.env` 或系统环境变量）；未配置时所有 `/api/*` 接口不鉴权

### 3. `config/pgvector.yml`

- `candidate_k`：初检候选数（默认 10），向量检索取该数量后做 Rerank
- `collection_name_768` / `collection_name_1024`：向量集合名
- `data_path`：上传文件临时目录
- `allow_knowledge_file_type`：允许的文件类型（默认 `["txt", "pdf"]`）
- `chunk_size` / `chunk_overlap`：文本切分参数
- `separators`：切分分隔符
- `k`：检索返回数量（默认 3）

### 4. `config/rag.yml`

- `chat_model_name`：Agent 主模型 / 检索 Agent 模型（默认 `deepseek-v4-flash`，DeepSeek）
- `embedding_model_name`：嵌入模型（默认 `BAAI/bge-m3`，SiliconFlow）
- `rerank_model_name` / `rerank_top_n` / `rerank_score_min`：Rerank 配置
- `retrieval_cache_maxsize` / `retrieval_cache_ttl`：检索结果缓存
- `query_rewrite_enabled`：是否启用检索词改写（改写走本地 Ollama）

### 5. `config/database.yml`

- `async_pool_size` / `async_max_overflow` / `pool_recycle` / `pool_pre_ping`
- `max_messages` / `max_tokens` / `llm_max_concurrency`
- `conversation_memory_enabled`：会话记忆总开关，默认 `true`
- `topic_router_enabled`：主题路由开关，默认 `true`
- `long_term_memory_enabled`：长期偏好开关，默认 `true`
- `summary_enabled`：主题摘要开关，默认 `true`
- `topic_recent_turns` / `context_max_tokens`：最近轮数与上下文 token 上限
- `memory_confidence_threshold` / `memory_max_items`：长期记忆置信度阈值与注入条数上限

`conversation_memory_enabled=false` 时只保留原有消息问答链路，主题、摘要和长期偏好均不创建或更新。

### 6. `config/prompts.yml`

所有提示词文件路径：`main_prompt_path`、`guard_prompt_path`、`scope_check_prompt_path`、`refusal_template_path`、`query_rewrite_prompt_path`、`retrieval_prompt_path`、`topic_router_prompt_path`、`summary_prompt_path`、`memory_prompt_path`。

---

## 安装与启动

### 方式一：使用 `uv`（推荐）

```powershell
uv sync
uv run uvicorn main:app --reload
```

### 方式二：使用 `pip`

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn main:app --reload
```

### 启动后访问

- 前端页面：`http://127.0.0.1:8000/`
- OpenAPI 文档：`http://127.0.0.1:8000/docs`

---

## 接口说明

### 接口鉴权

所有 `/api/*` 接口（文件、会话、聊天）均要求请求头 `X-API-Key`。服务端配置 `API_KEYS`（逗号分隔）后即启用校验，缺失或错误的 key 返回 401；`API_KEYS` 未配置时保持不鉴权，便于本地开发。前端在“设置”弹窗中填写并保存 API Key（保存于浏览器 `localStorage`）。

### 文件上传并入库

**POST** `/api/files/upload`

表单参数：

- `file`：上传文件
- `chunk_size`：可选，默认取配置
- `chunk_overlap`：可选，默认取配置

返回示例：

```json
{
  "message": "文件解析、切分并写入向量库成功",
  "filename": "your_document.pdf",
  "chunks": ["<file_id>-chunk0", "<file_id>-chunk1"],
  "file_id": "<file_id>"
}
```

> `chunks` 为该文件写入向量的 chunk id 列表，列表长度即片段数；`file_id` 为 `uploaded_files` 中的记录 id。

### 获取已上传文件列表

**GET** `/api/files/list`

返回示例：

```json
{
  "files": [
    {
      "id": "d8e8a22d-8568-4fa2-b2c5-0183cf6b7089",
      "filename": "洗涤养护.txt",
      "size": 6,
      "chunks": 17
    }
  ]
}
```

> `size` 单位为 KB，`chunks` 为该文件的向量片段数（INNER JOIN `langchain_pg_embedding` 统计）。前端根据这些值换算显示。

### 删除文件记录

**DELETE** `/api/files/{file_id}`

先删除 `uploaded_files` 记录（记录不存在则 404，不触碰向量），再删除 PGVector 中该文件的向量数据，同一事务保证原子性。

### 多轮问答

**POST** `/api/chat/`

```json
{
  "message": "纯棉T恤怎么洗不容易缩水？",
  "chatId": null
}
```

返回示例：

```json
{
  "answer": "建议冷水手洗，避免高温烘干...",
  "sources": ["纯棉洗涤.txt"],
  "chatId": "uuid",
  "topicId": "uuid",
  "topicAction": "CONTINUE"
}
```

`topicAction` 可能为 `CONTINUE`、`NEW_TOPIC`、`MIXED`、`CLARIFY` 或 `OUT_OF_SCOPE`。现有前端可以忽略 `topicId` 和 `topicAction`，不影响兼容性。`user_id` 可随请求体传入，用于长期偏好归属；默认值为 `anonymous`。

### 其他接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/conversations` | 创建会话 |
| GET | `/api/conversations?user_id=anonymous` | 获取会话列表 |
| GET | `/api/chat/{conversation_id}/messages` | 获取会话消息 |
| GET | `/api/chat/{conversation_id}/topics` | 获取主题列表，不返回摘要原文 |
| GET | `/api/chat/{conversation_id}/topics/{topic_id}` | 获取主题详情和摘要 |
| POST | `/api/chat/{conversation_id}/topics/{topic_id}/archive` | 归档主题 |
| GET | `/api/memory?user_id=anonymous` | 获取用户长期偏好 |
| DELETE | `/api/memory/{memory_id}?user_id=anonymous` | 删除一条长期偏好 |
| DELETE | `/api/memory?user_id=anonymous` | 清除用户全部长期偏好 |
| DELETE | `/api/chat/{chat_id}` | 删除会话 |

---

## 数据流与工作原理

### 文档入库流程

1. 用户调用 `POST /api/files/upload`
2. 文件类型通过 `core/validators.py` 校验
3. 流式写入 `data/` 临时文件，同时计算 MD5
4. MD5 命中已有记录则拒绝重复入库
5. 调用 `VectorStoreService.load_document()` 读取文件、切分、写入 PGVector（同步 PGVector，走线程池避免阻塞事件循环）
6. `FileRepository` 记录文件元数据（走异步 ORM 会话，请求结束时统一提交）；此步失败会**补偿删除**刚写入的向量
7. 删除临时文件

> **注意**：向量写入与 `uploaded_files` 记录分属两个连接/事务，无法做到严格 ACID。失败时通过补偿删除 + 对账脚本兜底：`uv run python scripts/reconcile_embeddings.py`（dry-run）或加 `--apply` 实际清理孤立向量。

### 问答流程

1. 用户调用 `POST /api/chat/`
2. 已有 `chatId` 先确认会话存在，并读取 active topic、最近有效轮次和未过期长期偏好
3. **TopicRouter** 只接收当前问题和受限上下文，输出主题动作、意图、范围和 `canonical_query`
4. `CLARIFY` 直接返回澄清；`OUT_OF_SCOPE` 返回拒答；`MIXED` 只把服装子问题交给后续检索
5. **L0 预检**：`GuardAgent.check_question_scope()` 作为主题路由后的域边界兜底
6. `NEW_TOPIC` 归档旧主题并创建新主题；`CONTINUE` 复用当前 active topic
7. **L1 检索**：`RetrievalAgent.retrieve()`（向量宽松召回 candidate_k → Rerank 精排 → `rerank_score_min` 过滤；失败降级为向量 top_n）
8. **L2 Agent**：`ReactAgent` 只接收标注过的当前问题、主题摘要、最近有效轮次、用户偏好和检索结果；不读取其他主题原始消息
9. **L3 兜底**：回答经 `GuardAgent.check()` 检查，越界回答替换为统一拒答并标记不可用
10. 放行回答保存为一对带相同 `turn_id` 的 Human/AI 消息；随后更新摘要和长期偏好，摘要失败不影响当前回答

### 文件删除流程

1. 调用 `DELETE /api/files/{file_id}`
2. 先删除 `uploaded_files` 记录；记录不存在则返回 404，不触碰向量
3. 再删除 PGVector 中该文件的向量数据
4. 文件记录与 PGVector 属于不同存储事务，失败时依靠补偿删除和 `scripts/reconcile_embeddings.py` 对账清理；不能宣称严格 ACID

---

## 常见问题

### 1. 上传文件后没有效果怎么办？

先检查：
- 文件类型是否在 `allow_knowledge_file_type` 里
- `data/` 是否可写
- PostgreSQL 是否连通、PGVector 是否可用
- 模型服务接口是否可达

### 2. 问答接口报错怎么办？

常见原因：
- 数据库连接失败
- 模型名称配置错误
- `SILICONFLOW_API_KEY` 或 `DEEPSEEK_API_KEY` 未设置
- `chatId` 格式不合法

### 3. 域内问题被误拦截怎么办？

- L0 误拦：检查 `prompts/scope_check_prompt.txt` 正面示例是否覆盖该场景，或调整 `_parse_scope_label` 优先级
- L1 文档不足：降低 `rerank_score_min`（当前 0.05），或增加知识库文档
- L3 误杀：检查 `prompts/guard_prompt.txt` 示例，或调整 `rerank_score_min`

### 4. 为什么会看到 `304 Not Modified`？

这是浏览器缓存命中，表示静态资源没有变化。更新静态资源后使用强制刷新（`Ctrl+Shift+R`）。

### 5. 表结构需要手动创建吗？

是的。`conversations`、`messages`、`uploaded_files` 需手动执行 DDL。`langchain_pg_embedding` 和 `langchain_pg_collection` 由 PGVector 自动创建。参考 `scripts/data_test.sql`。

### 6. 越界问题被放行 / L0 拦截失效怎么办？

检查本地 Ollama 是否已启动（`ollama serve`）且已拉取 `qwen3.5:4b` 模型。Ollama 未启动时，L0/L3 会静默放行（解析失败默认 IN），越界拦截将失效。

### 7. 接口返回 401 怎么办？

服务端已配置 `API_KEYS` 时，所有 `/api/*` 请求必须携带 `X-API-Key` 请求头。前端在“设置”中填写与 `API_KEYS` 中任一值一致的 Key 即可；命令行调用示例：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/files/list -Headers @{ "X-API-Key" = "your-key" }
```

---

## 许可证

MIT License

Copyright (c) 2026
