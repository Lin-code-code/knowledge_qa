# RAG智能问答系统

一个基于 **FastAPI + LangChain + PGVector** 的知识库问答项目。

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

项目结构清晰，适合作为：

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
- **LangChain Community / LangChain PGVector / LangChain Ollama**：模型与向量相关能力
- **DashScope**：部分模型能力
- **PyYAML**：YAML 配置加载
- **PyPDF**：PDF 解析

---

## 项目结构

```text
FastAPI_chunking/
├─ main.py                    # FastAPI 应用入口
├─ pyproject.toml             # 项目依赖与构建配置
├─ uv.lock                    # uv 锁定文件
├─ agent/                     # 智能代理组件
│  ├─ react_agent.py          # ReactAgent 实现
│  └─ tool/
│     ├─ agent_tools.py       # Agent 工具(如 rag_summarize, 时间查询等)
│     └─ middleware.py
├─ history/                   # 会话历史相关逻辑
│  ├─ __init__.py
│  ├─ models.py               # 历史消息相关模型
│  └─ db/
│     ├─ __init__.py
│     ├─ engine.py           # 数据库引擎
│     └─ message_store.py    # 消息存储实现
├─ config/
│  ├─ pgvector.yml            # 数据库、切分、文件类型等配置
│  ├─ rag.yml                 # 模型配置
│  └─ prompts.yml             # 提示词文件路径配置
├─ data/                      # 上传文件临时目录 / 知识文件目录
├─ logs/                      # 运行日志目录
├─ model/
│  └─ factory.py              # 聊天模型与嵌入模型工厂
├─ prompts/
│  └─ rag_summarize.txt       # RAG 提示词模板
├─ rag/
│  ├─ rag_service.py          # RAG 服务封装
│  └─ vector_store.py         # PGVector 文档入库与检索
├─ routers/
│  ├─ files.py                # 文件上传接口
│  └─ chat.py                 # 问答与会话接口
├─ schemas/
│  └─ chat.py                 # 请求/响应数据结构
├─ static/
│  ├─ index.html              # 前端页面入口
│  ├─ css/
│  └─ js/
└─ utils/
   ├─ config_handler.py       # YAML 配置加载
   ├─ file_handler.py         # 文档读取、MD5、文件处理
   ├─ load_env.py             # `.env` 环境变量读取
   ├─ logger_handler.py       # 日志封装
   └─ path_tool.py            # 路径工具
```

---

## 运行要求

### 基础环境

- Python 3.13+
- PostgreSQL 数据库
- 已启用 PGVector 扩展
- 可访问的模型服务

### 模型依赖

当前代码使用：

- `ChatTongyi` 作为聊天模型
- `OllamaEmbeddings` 作为嵌入模型

模型名称由 `config/rag.yml` 控制。如果你切换模型服务，需要同步调整：

- `config/rag.yml`
- `model/factory.py`

---

## 配置说明

### 1. 环境变量 `.env`

`utils/load_env.py` 会从项目根目录读取 `.env` 文件。

建议创建如下内容：

```env
HOST=127.0.0.1
PORT=5432
USER=postgres
PASSWORD=your_password
DB=vectordb
```

> 请根据你的 PostgreSQL 实际账号、密码和数据库名修改。

### 2. `config/pgvector.yml`

该文件用于控制数据库和文档处理行为，包含：

- 数据库连接信息
- `collection_name`
- `data_path`
- `md5_hex_store`
- `allow_knowledge_file_type`
- `chunk_size` / `chunk_overlap`
- `separators`

通常你最需要调整的是：

- `host`
- `port`
- `dbname`
- `user`
- `password`
- `allow_knowledge_file_type`
- `chunk_size`
- `chunk_overlap`

### 3. `config/rag.yml`

该文件主要配置模型名称：

- `chat_model_name`
- `embedding_model_name`
- `ol_chat_model_name`
- `ol_embedding_model_name`

### 4. `config/prompts.yml` 和 `prompts/rag_summarize.txt`

- `config/prompts.yml` 指定提示词文件路径
- `prompts/rag_summarize.txt` 是 RAG 生成模板

模板会注入：

- 用户问题 `{input}`
- 检索上下文 `{context}`

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
  "chunks": []
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

1. 用户调用 `/api/files/upload`
2. 文件先保存到 `data/`
3. 根据配置校验文件类型
4. 读取文件内容并切分
5. 写入 PGVector
6. 记录文件 MD5，防止重复导入
7. 删除临时文件

### 问答流程

1. 用户调用 `/api/chat/`
2. 系统读取最近对话历史
3. 将对话历史和最新问题传递给 `ReactAgent`
4. `ReactAgent` 分析意图，自主决定是否需要使用工具（如调用向量检索服务获取背景知识片段）
5. Agent 结合系统背景设定、检索获取的文档和用户问题合成最终回答
6. 接口同时返回所调用的相关知识库片段元数据（Sources）
7. 把用户消息和模型回答写回会话存储

---

## 开发与贡献

欢迎提交 Issue 和 Pull Request。建议遵循以下原则：

- 提交前先确认配置不会暴露真实密钥
- 改模型相关代码时，优先检查 `model/factory.py`
- 改检索与切分逻辑时，优先检查 `rag/vector_store.py`
- 改提示词时，优先检查 `prompts/rag_summarize.txt`
- 扩展接口时，记得同步更新 `schemas/chat.py`

如果你准备贡献代码，建议先在本地完成：

```powershell
uv run python -m py_compile main.py
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

### 3. 为什么会看到 `304 Not Modified`？

这是浏览器缓存命中，表示静态资源没有变化，属于正常现象。

### 4. 为什么关闭应用时会执行数据库关闭？

`main.py` 使用了 FastAPI `lifespan`，应用退出时会执行 `close_db()` 来释放数据库资源。

---

## 许可证

如未另行说明，默认按项目内部使用或作者指定许可证处理。若你准备对外开源，建议在仓库中补充明确许可证文件（如 MIT / Apache-2.0）。

---

## 致谢

感谢 FastAPI、LangChain、PostgreSQL、PGVector 及相关开源生态。
