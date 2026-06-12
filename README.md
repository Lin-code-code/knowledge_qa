# RAG智能问答系统

一个基于 **Python + FastAPI + LangChain + PGVector** 的知识库问答项目。

它支持：

- 上传文档并自动切分入库
- 基于向量检索的 RAG 问答
- 多轮对话与会话管理
- 静态前端页面入口
- 使用 PostgreSQL + PGVector 作为向量存储

---

## 目录

- [项目概览](#项目概览)
- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [运行要求](#运行要求)
- [配置说明](#配置说明)
- [安装与启动](#安装与启动)
- [接口说明](#接口说明)
- [数据流与工作原理](#数据流与工作原理)
- [开发与贡献](#开发与贡献)
- [常见问题](#常见问题)

---

## 项目概览

`FastAPI_chunking` 的目标是提供一套可扩展的知识库问答后端：

1. 用户上传知识文件
2. 系统读取文件并按配置切分文本
3. 切分后的内容写入 PGVector
4. 用户提问时，系统先检索相关知识片段
5. 将检索结果交给大模型生成回答

项目采用分层架构（API → Service → Repository），职责清晰，适合作为：

- RAG 项目样板
- FastAPI + PostgreSQL 向量库实践项目
- 企业内部知识问答系统原型

---

## 功能特性

### 文档上传与入库

- 支持上传知识文件
- 目前默认支持 `txt`、`pdf`
- 上传后先保存到 `data/` 目录
- 使用 `RecursiveCharacterTextSplitter` 自动切分
- 切分结果写入 PGVector
- 使用 MD5 记录做去重，避免重复入库
- 前端文件列表仅展示后端接口返回结果

### 知识库问答

- 基于向量检索召回相关内容
- 支持基于 ReactAgent 代理模式进行意图识别和工具调用
- 使用提示词模板组织回答
- 支持多轮对话上下文
- 支持返回会话 ID，便于前端继续追问

### 会话管理

- 创建会话
- 获取会话列表
- 获取某个会话的消息列表
- 删除会话及其消息

### 前端入口

- 根路径 `/` 返回 `static/index.html`
- `/static` 挂载静态资源目录

---

## 技术栈

- **Python** >= 3.13
- **FastAPI**：API 服务
- **Uvicorn**：ASGI 服务器
- **SQLAlchemy** + **asyncpg**：异步数据库访问
- **PostgreSQL + PGVector**：向量存储
- **LangChain & LangGraph**：Agent编排与大模型调度
- **LangChain Community / LangChain PGVector**：模型与向量相关能力
- **DashScope (ChatTongyi)**：默认聊天模型
- **SiliconFlow OpenAI API**：默认嵌入模型（OpenAIEmbeddings）
- **Ollama**：可选本地模型/嵌入
- **PyYAML**：YAML 配置加载
- **PyPDF**：PDF 解析

---

## 项目结构

```text
FastAPI_chunking/
├─ main.py                     # FastAPI 应用入口
├─ pyproject.toml              # 项目依赖与构建配置
├─ uv.lock                     # uv 锁定文件
│
├─ core/                       # ★ 基础设施（原 utils/ 拆分）
│  ├─ config.py                # EnvConfig + 懒加载 YAML 配置
│  ├─ logger.py                # 日志封装（控制台 + 按天轮转文件）
│  ├─ paths.py                 # 路径工具（项目根目录发现）
│  └─ validators.py            # 通用校验函数（文件扩展名等）
│
├─ models/                     # ★ ORM 模型（原 history/models 拆分）
│  ├─ base.py                  # DeclarativeBase
│  ├─ conversation.py          # Conversation + Message
│  └─ uploaded_file.py         # UploadedFile
│
├─ db/                         # ★ 数据访问层（原 history/db/）
│  ├─ engine.py                # 异步数据库引擎与 session 工厂
│  ├─ session.py               # get_db() / close_db() 依赖注入
│  ├─ conversation_repo.py     # ConversationRepository（会话 CRUD）
│  └─ file_repo.py             # FileRepository（文件记录 CRUD + 向量删除）
│
├─ services/                   # ★ 业务编排层（新增，从 api/ 提取）
│  ├─ chat_service.py          # ChatService：多轮问答业务流程
│  └─ document_service.py      # DocumentService：文件上传入库流程
│
├─ api/                        # ★ API 层（原 routers/ 重命名 + 瘦身）
│  ├─ chat.py                  # 问答与会话接口（仅 HTTP 适配）
│  └─ documents.py             # 文件上传/列表/删除接口
│
├─ agent/                      # 智能代理组件
│  ├─ react_agent.py           # ReactAgent（LangGraph 实现）
│  └─ tool/
│     ├─ agent_tools.py        # Agent 工具（rag_summarize, 时间查询）
│     └─ middleware.py         # 工具调用监控与日志
│
├─ rag/                        # RAG 检索
│  ├─ rag_service.py           # RAG 服务（检索 + 生成）
│  ├─ vector_store.py          # PGVector 文档入库与向量检索
│  └─ model/
│     └─ factory.py            # 聊天/嵌入模型工厂（ChatTongyi, Ollama, SiliconFlow）
│
├─ config/                     # YAML 配置（不含数据库密码等敏感信息）
│  ├─ pgvector.yml             # 切分、文件类型、集合名配置
│  ├─ rag.yml                  # 模型名称配置
│  ├─ prompts.yml              # 提示词文件路径
│  └─ database.yml             # 连接池与对话管理参数
│
├─ utils/                      # 保留工具（未迁移）
│  ├─ file_handler.py          # 文档读取、MD5 计算
│  └─ prompt_loader.py         # 提示词模板文件加载
│
├─ schemas/
│  └─ chat.py                  # Pydantic 请求/响应模型
│
├─ prompts/
│  ├─ main_prompt.txt          # Agent 系统提示词
│  └─ rag_summarize.txt        # RAG 摘要提示词模板
│
├─ static/                     # 前端静态文件
│  ├─ index.html               # SPA 入口
│  ├─ css/
│  └─ js/
│
├─ data/                       # 上传文件临时目录
├─ logs/                       # 运行日志（按天轮转，保留 30 天）
└─ tests/                      # 测试目录
   ├─ conftest.py
   ├─ unit/
   └─ integration/
```

---

## 运行要求

### 基础环境

- Python 3.13+
- PostgreSQL 数据库
- 已启用 PGVector 扩展
- 可访问的模型服务（DashScope 或 SiliconFlow）

### 模型依赖

当前代码默认使用：

- `ChatTongyi` 作为聊天模型（DashScope）
- `OpenAIEmbeddings` 作为嵌入模型（SiliconFlow API）

模型名称由 `config/rag.yml` 控制。如果你切换模型服务，需要同步调整：

- `config/rag.yml`
- `rag/model/factory.py`

---

## 配置说明

### 1. `.env` 环境变量（数据库凭据）

数据库连接信息统一从项目根目录的 `.env` 文件读取，**不再存储在 YAML 配置中**：

```
HOST=192.168.1.100
PORT=5432
USER=postgres
PASSWORD=your_password
DB=vectordb
```

如果使用 SiliconFlow，还需要设置系统环境变量（非 `.env`）：

- `SILICONFLOW_API_KEY`

### 2. `config/pgvector.yml`

该文件控制文档切分与向量存储行为：

- `collection_name_768` / `collection_name_1024`
- `data_path`
- `allow_knowledge_file_type`
- `chunk_size` / `chunk_overlap`
- `separators`
- `k`（检索返回数量）

### 3. `config/database.yml`

该文件用于会话与文件记录的异步连接池参数：

- `async_pool_size` / `async_max_overflow` / `pool_recycle` / `pool_pre_ping`
- `max_messages` / `max_tokens`

### 4. `config/rag.yml`

该文件主要配置模型名称：

- `chat_model_name`
- `embedding_model_name`
- `ol_chat_model_name`
- `ol_embedding_model_name`

### 5. `config/prompts.yml` 和 `prompts/rag_summarize.txt`

- `config/prompts.yml` 指定提示词文件路径
- `prompts/rag_summarize.txt` 是 RAG 生成模板

模板会注入：

- 用户问题 `{input}`
- 检索上下文 `{context}`

---

## 安装与启动

### 数据库初始化

确保 PostgreSQL 已启用 PGVector 扩展：

```powershell
psql -h <host> -U <user> -d <dbname> -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

应用启动后，ORM 模型会自动创建 `conversations`、`messages`、`uploaded_files` 表（需确保数据库用户有建表权限）。

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
- ReDoc：`http://127.0.0.1:8000/redoc`

---

## 接口说明

### 文件上传并入库

**POST** `/api/files/upload`

表单参数：

- `file`：上传文件
- `chunk_size`：可选，默认取配置
- `chunk_overlap`：可选，默认取配置

示例：

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/files/upload" -F "file=@your_document.pdf"
```

返回示例：

```json
{
  "message": "文件解析、切分并写入向量库成功",
  "filename": "your_document.pdf",
  "chunks": [],
  "file_id": "uuid"
}
```

### 获取已上传文件列表

**GET** `/api/files/list`

返回示例：

```json
{
  "files": [
    {
      "id": "uuid",
      "filename": "your_document.pdf",
      "size": 123,
      "uploaded_at": "2026-05-28T02:40:10.399516+00:00",
      "md5_hex": "..."
    }
  ]
}
```

> `size` 为 KB。前端根据该值换算显示。

### 删除文件记录

**DELETE** `/api/files/{file_id}`

返回示例：

```json
{
  "message": "文件记录已删除"
}
```

### 创建会话

**POST** `/api/conversations`

```json
{
  "user_id": "anonymous",
  "title": "新对话"
}
```

### 获取会话列表

**GET** `/api/conversations?user_id=anonymous`

### 获取会话消息

**GET** `/api/chat/{conversation_id}/messages`

### 多轮问答

**POST** `/api/chat/`

```json
{
  "message": "扫地机器人是如何实现自主导航的？",
  "chatId": null
}
```

返回示例：

```json
{
  "answer": "...",
  "sources": [],
  "chatId": "..."
}
```

### 删除会话

**DELETE** `/api/chat/{chat_id}`

---

## 数据流与工作原理

### 文档入库流程

1. 用户调用 `api/documents.py` 的 `/api/files/upload`
2. 文件类型通过 `core/validators.py` 校验
3. 流式写入 `data/`（边写边算 MD5，避免大文件 OOM）
4. 写入 MD5 到文件记录表，通过 `db/file_repo.py` 去重
5. 调用 `rag/vector_store.py` 读取文件内容并切分
6. 切分结果写入 PGVector
7. 删除临时文件

### 问答流程

1. 用户调用 `api/chat.py` 的 `/api/chat/`
2. `services/chat_service.py` 编排业务流程
3. `db/conversation_repo.py` 读取最近对话历史（含 token 窗口裁剪）
4. 将对话历史和最新问题传递给 `ReactAgent`
5. `ReactAgent` 分析意图，自主决定是否调用工具（如通过 `rag_summarize` 检索知识库）
6. Agent 合成最终回答
7. 接口同时返回相关知识库来源（Sources）
8. 用户消息和模型回答写回会话存储

---

## 开发与贡献

欢迎提交 Issue 和 Pull Request。建议遵循以下原则：

- 提交前先确认配置不会暴露真实密钥
- 数据库凭据统一放在 `.env`，YAML 配置只放非敏感参数
- 改模型相关代码时，优先检查 `rag/model/factory.py`
- 改检索与切分逻辑时，优先检查 `rag/vector_store.py`
- 改业务编排逻辑时，优先检查 `services/`
- 改提示词时，优先检查 `prompts/rag_summarize.txt`
- 扩展接口时，记得同步更新 `schemas/chat.py`
- 新增 API 端点时，路由写在 `api/`，业务逻辑写在 `services/`

如果你准备贡献代码，建议先在本地完成：

```powershell
uv run python -m py_compile main.py
```

### 运行测试

```powershell
uv run pytest tests/
```

---

## 常见问题

### 1. 上传文件后没有效果怎么办？

先检查：

- 文件类型是否在 `allow_knowledge_file_type` 里
- `data/` 是否可写
- PostgreSQL 是否连通
- PGVector 是否可用
- 模型服务是否启动

### 2. 问答接口报错怎么办？

常见原因：

- 数据库连接失败
- 模型名称配置错误
- 嵌入模型不可用
- `chatId` 或 `conversation_id` 格式不合法

### 3. 向量检索报错或无结果怎么办？

常见原因：

- 未设置 `SILICONFLOW_API_KEY`（系统环境变量）
- `config/rag.yml` 中嵌入模型名称不可用
- `.env` 中数据库连接参数不正确

### 4. 为什么会看到 `304 Not Modified`？

这是浏览器缓存命中，表示静态资源没有变化，属于正常现象。更新静态资源后可使用强制刷新。

### 5. 为什么关闭应用时会执行数据库关闭？

`main.py` 使用了 FastAPI `lifespan`，应用退出时会调用 `db.session.close_db()` 来释放数据库资源。

---

## 许可证

MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
