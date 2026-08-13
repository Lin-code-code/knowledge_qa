# 服装垂直客服 RAG 问答系统

基于 **Python + FastAPI + LangChain + PGVector** 的服装行业智能问答系统，带三层安全防乱说话架构。

---

## 目录

- [项目概览](#项目概览)
- [功能特性](#功能特性)
- [三层防乱说话架构](#三层防乱说话架构)
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

`FastAPI_chunking` 是一套服装行业垂直客服系统，支持上传知识文件、向量检索、多轮问答，并内置三层安全机制防止大模型胡说八道：

1. 用户上传服装知识文件（尺码表、洗护说明、面料介绍等）
2. 系统读取文件并按配置切分文本，写入 PGVector
3. 用户提问时，先经 L0 域内预检判定是否属于服装领域
4. 越界问题直接拒答（不入库、不调 Agent）
5. 域内问题经向量检索 + Rerank 精排后交给 Agent 生成回答
6. 回答经 L3 分类器兜底，越界输出替换为统一拒答话术

---

## 功能特性

### 三层防乱说话

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
- 支持多轮对话上下文（自动过滤历史拒答记录）
- 检索结果带缓存（可配置 TTL 与容量上限）
- 支持返回会话 ID，便于前端继续追问

### 会话管理

- L0 越界提问与 L3 拦截的越界回答均不创建会话、不入库（仅 L3 放行的问答才落库）
- 创建会话、获取会话列表
- 获取某个会话的消息列表
- 删除会话及其消息

### 前端入口

- 根路径 `/` 返回 `static/index.html`
- `/static` 挂载静态资源目录

---

## 三层防乱说话架构

```text
用户提问
    |
    v
+--------------------------------------+
|  L0 域内预检 (GuardService)              |   ← 本地 Ollama qwen3.5:4b
|  YES/NO 分类                           |       解析失败默认放行
|  越界 → 直接返回拒答，不入库                     |
+-------------------+------------------+
                    | 域内
                    |
    v
+--------------------------------------+
|  L1 检索 + Rerank                      |
|  candidate_k → Rerank 精排             |
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
|  L3 分类器 (GuardService)               |   ← 本地 Ollama qwen3.5:4b
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
- **DeepSeek**：主聊天模型（ReactAgent）
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
│  └─ validators.py            # 通用校验函数（文件扩展名等）
│
├─ models/                     # ORM 模型
│  ├─ base.py                  # DeclarativeBase
│  ├─ conversation.py          # Conversation + Message
│  └─ uploaded_file.py         # UploadedFile
│
├─ db/                         # 数据访问层
│  ├─ engine.py                # 异步数据库引擎与 session 工厂
│  ├─ session.py               # get_db() / close_db() 依赖注入
│  ├─ conversation_repo.py     # ConversationRepository（会话 CRUD）
│  └─ file_repo.py             # FileRepository（文件记录 CRUD + 向量删除）
│
├─ services/                   # 业务编排层
│  ├─ chat_service.py          # ChatService：L0 预检 + Agent + L3 兜底
│  └─ guard_service.py         # GuardService：L0 域内预检 + L3 输出分类器
│
├─ api/                        # API 层
│  ├─ chat.py                  # 问答与会话接口
│  └─ documents.py             # 文件上传/列表/删除接口
│
├─ agent/                      # 智能代理组件
│  ├─ react_agent.py           # ReactAgent（LangGraph 实现）
│  ├─ rewrite_agent.py         # RewriteAgent（query 改写，create_agent 封装）
│  ├─ retrieval_agent.py       # RetrievalAgent（向量检索+Rerank，create_agent 封装）
│  └─ tool/
│     ├─ agent_tools.py        # Agent 工具（rag_summarize, 时间查询）
│     └─ middleware.py         # 工具调用监控与日志
│
├─ rag/                        # RAG 检索与模型工厂
│  ├─ rag_service.py           # RAG 服务（检索 + Rerank + TTL 缓存）
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
│  └─ chat.py                  # Pydantic 请求/响应模型
│
├─ prompts/                    # 提示词模板
│  ├─ main_prompt.txt          # Agent 系统提示词（服装垂直客服）
│  ├─ rag_summarize.txt        # RAG 检索提示词
│  ├─ guard_prompt.txt         # L3 分类器 prompt
│  ├─ scope_check_prompt.txt   # L0 域内预检 prompt
│  └─ refusal_template.txt     # 统一拒答话术
│
├─ static/                     # 前端静态文件
│  ├─ index.html               # SPA 入口
│  ├─ css/
│  └─ js/
│
├─ scripts/                     # 运维脚本
│  ├─ create_hnsw_index.py      # 为 langchain_pg_embedding 创建 HNSW 索引
│  └─ reconcile_embeddings.py   # 清理孤儿向量（上传失败兜底，--apply 执行删除）
│
├─ data/                       # 上传文件临时目录
├─ logs/                       # 运行日志（按天轮转，保留 30 天）
└─ tests/                      # 测试目录（待补充）
```

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
- `DEEPSEEK_API_KEY`：用于主聊天模型（ReactAgent）

### 3. `config/pgvector.yml`

- `candidate_k`：初检候选数（默认 10），向量检索取该数量后做 Rerank
- `collection_name_768` / `collection_name_1024`：向量集合名
- `data_path`：上传文件临时目录
- `allow_knowledge_file_type`：允许的文件类型（默认 `["txt", "pdf"]`）
- `chunk_size` / `chunk_overlap`：文本切分参数
- `separators`：切分分隔符
- `k`：检索返回数量（默认 3）

### 4. `config/rag.yml`

- `chat_model_name`：Agent 主模型（默认 `deepseek-v4-flash`，DeepSeek）
- `embedding_model_name`：嵌入模型（默认 `BAAI/bge-m3`，SiliconFlow）
- `rerank_model_name` / `rerank_top_n` / `rerank_score_min`：Rerank 配置
- `retrieval_cache_maxsize` / `retrieval_cache_ttl`：检索结果缓存
- `query_rewrite_enabled`：是否启用检索词改写（改写走本地 Ollama）

### 5. `config/database.yml`

- `async_pool_size` / `async_max_overflow` / `pool_recycle` / `pool_pre_ping`
- `max_messages` / `max_tokens` / `llm_max_concurrency`

### 6. `config/prompts.yml`

所有提示词文件路径：`main_prompt_path`、`guard_prompt_path`、`scope_check_prompt_path`、`refusal_template_path`、`query_rewrite_prompt_path`。

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

先删除 PGVector 中该文件的向量数据，再删除文件记录，同一事务保证原子性。

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
  "chatId": "uuid"
}
```

> L0 越界拦截：域外问题直接返回拒答话术，不创建会话、不入库。

### 其他接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/conversations` | 创建会话 |
| GET | `/api/conversations?user_id=anonymous` | 获取会话列表 |
| GET | `/api/chat/{conversation_id}/messages` | 获取会话消息 |
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
2. **L0 预检**：`GuardService.check_question_scope()` 用轻量模型判定问题是否属于服装领域；越界直接返回拒答，不入库、不创建会话
3. 已有会话则获取最近历史（自动过滤拒答问答对；`agent_history_turns=0` 时实际不传给 agent）
4. **L1 检索**：`RetrievalAgent.retrieve()`（create_agent，工具 `vector_search` 宽松召回 candidate_k → `rerank` 精排 → rerank_score >= rerank_score_min 过滤；LLM 只驱动工具调用，文档经 contextvar 回传；agent 失败降级为向量 top_n）
5. **L2 Agent**：`ReactAgent` 接收历史 + 问题，通过 `rag_summarize` 工具获取原文资料（不做 LLM 总结），自行分析匹配回答；检索到的来源在请求内收集（contextvar，按请求隔离）
6. **L3 兜底**：Agent 回答经 `GuardService.check()` 检查，越界（OUT）替换为统一拒答模板，且**不创建会话、不入库**
7. L3 放行后才创建/复用会话，返回 `(answer, sources, chatId)`，消息写入历史（由 `get_db()` 统一提交）

### 文件删除流程

1. 调用 `DELETE /api/files/{file_id}`
2. 先删除 `uploaded_files` 记录；记录不存在则返回 404，不触碰向量
3. 再删除 PGVector 中该文件的向量数据
4. 两步同一事务，任一步失败整体回滚，避免孤立数据

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

---

## 许可证

MIT License

Copyright (c) 2026
