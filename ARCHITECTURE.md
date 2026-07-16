# 中医 AI Agent (zhongyi-ai) — 项目架构文档

> **编写时间**: 2026-07-09  
> **技术栈**: LangChain + 通义千问(Qwen) + Milvus + Neo4j + SQLite + FastAPI + Docker + uv

---

## 一、项目概述

本项目是一个**中医 AI 智能助手**，核心功能包括：

1. **智能辨证**：根据用户症状描述进行中医辨证分析
2. **方剂推荐**：基于症状推荐经典方剂（含组成、用法、出处）
3. **药材查询**：查询单味药材的性味归经、功效、禁忌
4. **穴位推荐**：根据症状推荐按摩/艾灸穴位
5. **体质分析**：判断用户体质类型，给出调理建议

---

## 二、项目目录结构

```
zhongyi_ai/
├── src/                          # 源码目录
│   ├── config.py                 # [配置层] pydantic-settings 全局配置
│   ├── agent/                    # [Agent 层] LangChain Agent 核心
│   │   ├── llm.py                #   通义千问 ChatModel 封装
│   │   └── core.py               #   Agent 创建 + System Prompt
│   ├── rag/                      # [RAG 层] 向量检索
│   │   ├── embedding.py          #   sentence-transformers 向量化
│   │   ├── milvus_store.py       #   Milvus 向量库连接与管理
│   │   └── retriever.py          #   中医知识检索器
│   ├── graphrag/                 # [GraphRAG 层] 知识图谱检索（新增）
│   │   ├── graph_store.py        #   Neo4j 图数据库连接与操作
│   │   ├── graph_builder.py      #   从结构化数据构建知识图谱
│   │   ├── retriever.py          #   图检索器（治疗路径/实体关系）
│   │   └── seed_graph.py         #   知识图谱种子数据初始化
│   ├── tools/                    # [工具层] Agent 可调用的工具
│   │   ├── tcm_tools.py          #   方剂/药材/穴位/体质 4 个查询工具
│   │   └── graphrag_tools.py     #   知识图谱查询工具（新增）
│   ├── data/                     # [数据层] SQLite 结构化存储
│   │   ├── database.py           #   SQLite 数据库 CRUD 操作
│   │   └── seed.py               #   种子数据初始化脚本
│   └── api/                      # [API 层] FastAPI 对外服务
│       └── server.py             #   RESTful API (/chat, /chat/stream)
├── data/                         # 运行时数据
│   └── tcm.db                    #   SQLite 数据库文件
├── scripts/                      # 启动脚本
│   ├── start.bat                 #   Windows 启动
│   └── start.sh                  #   Linux/macOS 启动
├── Dockerfile                    # Docker 镜像构建 (uv 多阶段构建)
├── docker-compose.yml            # 容器编排 (Milvus + Neo4j + Agent)
├── pyproject.toml                # 项目元数据与依赖声明
├── .env / .env.example           # 环境变量配置
└── .gitignore                    # Git 忽略规则
```

---

## 三、技术架构总览

```
┌─────────────────────────────────────────────────────────┐
│                      用户 / 客户端                        │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP POST /chat  or  /chat/stream
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI (src/api/server.py)            │
│  - POST /chat         普通对话                            │
│  - POST /chat/stream  流式对话 (SSE)                      │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
           ▼                              ▼
┌──────────────────┐          ┌──────────────────────────┐
│  Agent 层         │          │  RAG 检索层                │
│  src/agent/core   │◄─────────│  src/rag/retriever.py     │
│  (LangChain Agent)│  注入    │  - 向量相似度检索          │
│  - System Prompt  │  知识    │  - 关键词匹配              │
│  - 工具绑定       │          │  - 融合排序                │
│  - 流式/非流式    │          └──────────┬───────────────┘
└────────┬─────────┘                      │
         │ 调用工具                        ▼
         ▼                   ┌──────────────────────────┐
┌──────────────────┐        │  Milvus 向量数据库          │
│  工具层            │        │  src/rag/milvus_store.py   │
│  src/tools/       │        │  - 连接管理                 │
│  tcm_tools.py     │        │  - Collection 创建          │
│  - 方剂查询       │        │  - 向量插入                 │
│  - 药材查询       │        │  - 相似度搜索               │
│  - 穴位查询       │        └────────────────────────────┘
│  - 体质查询       │                      ▲
└────────┬─────────┘                      │
         │                                │ 向量化
         ▼                                │
┌──────────────────┐          ┌──────────────────────────┐
│  SQLite 数据库     │          │  Embedding 模型            │
│  src/data/        │          │  src/rag/embedding.py     │
│  database.py      │          │  sentence-transformers    │
│  - 方剂 CRUD      │          │  BAAI/bge-small-zh-v1.5   │
│  - 药材 CRUD      │          └──────────────────────────┘
│  - 穴位 CRUD      │
│  - 体质 CRUD      │
└──────────────────┘
```

---

## 四、核心调用链路

### 4.1 启动流程

```
scripts/start.bat (或 start.sh)
  │
  ├─1. 启动 Docker 服务 (Milvus + etcd + MinIO)
  │     docker-compose up -d etcd minio milvus
  │
  ├─2. 初始化数据 (首次或重置时)
  │     uv run python -m src.data.seed
  │     ├── src/data/database.py → SQLite 建表 + 插入种子数据
  │     └── src/rag/milvus_store.py → Milvus 创建 Collection + 插入向量
  │
  └─3. 启动 API 服务
        uv run python -m src.api.server
        └── uvicorn 启动 FastAPI 在 0.0.0.0:8000
```

### 4.2 对话请求流程

```
用户发送 POST /chat { "message": "我头痛发烧" }
  │
  ▼
src/api/server.py
  │ ChatRequest 模型验证
  │ 从会话存储获取历史消息
  ▼
src/agent/core.py → create_tcm_agent()
  │
  ├─1. 创建 LLM: QwenChatModel (src/agent/llm.py)
  │     使用 DashScope API，模型 qwen-plus
  │
  ├─2. 加载工具 (src/tools/tcm_tools.py)
  │     - search_formula      方剂查询
  │     - search_herb         药材查询
  │     - search_acupoint     穴位查询
  │     - analyze_constitution 体质分析
  │
  ├─3. 构建 System Prompt (中医角色设定 + 辨证体系 + 安全规则)
  │
  ├─4. 注入 RAG 检索器 (src/rag/retriever.py)
  │     将 Milvus 检索结果作为知识上下文注入
  │
  └─5. 创建 LangChain Agent (create_tool_calling_agent + AgentExecutor)
  │
  ▼
Agent 执行
  │
  ├── LLM 分析用户意图
  │     │
  │     ├── 需要查询方剂 → 调用 search_formula 工具
  │     │     └── src/tools/tcm_tools.py → src/data/database.py → SQLite
  │     │
  │     ├── 需要查询药材 → 调用 search_herb 工具
  │     │     └── src/tools/tcm_tools.py → src/data/database.py → SQLite
  │     │
  │     ├── 需要查询穴位 → 调用 search_acupoint 工具
  │     │     └── src/tools/tcm_tools.py → src/data/database.py → SQLite
  │     │
  │     ├── 需要体质分析 → 调用 analyze_constitution 工具
  │     │     └── src/tools/tcm_tools.py → src/data/database.py → SQLite
  │     │
  │     └── 一般辨证推理 → LLM 直接回答
  │
  ▼
返回结果给 FastAPI → JSON 响应返回用户
```

### 4.3 RAG 检索流程

```
用户问题
  │
  ▼
src/rag/retriever.py → TCMRetriever.retrieve(query)
  │
  ├─1. 文本向量化
  │     src/rag/embedding.py → TCMEmbedding
  │     模型: BAAI/bge-small-zh-v1.5 (384维)
  │     将 query 转为向量
  │
  ├─2. Milvus 相似度搜索
  │     src/rag/milvus_store.py → TCMVectorStore.search()
  │     返回 top_k 条相似文档
  │
  ├─3. 关键词匹配增强
  │     在检索结果中做关键词二次过滤
  │
  ├─4. 融合排序
  │     向量相似度 + 关键词匹配度 → 最终排序
  │
  └─5. 格式化返回
       将检索到的中医知识片段拼接为上下文字符串
```

---

## 五、各模块详细说明

### 5.1 配置层 — `src/config.py`

| 类/方法 | 说明 |
|---------|------|
| `Settings` | pydantic-settings 配置类，从 `.env` 文件加载 |
| `DASHSCOPE_API_KEY` | 通义千问 API 密钥 |
| `QWEN_MODEL` | 模型名称，默认 `qwen-plus` |
| `MILVUS_HOST` / `MILVUS_PORT` | Milvus 连接地址，默认 `localhost:19530` |
| `MILVUS_COLLECTION` | Milvus Collection 名称，默认 `tcm_knowledge` |
| `SQLITE_PATH` | SQLite 数据库路径，默认 `data/tcm.db` |
| `HOST` / `PORT` | API 服务监听地址和端口 |

---

### 5.2 Agent 层

#### 5.2.1 `src/agent/llm.py` — 通义千问 LLM 封装

| 类/方法 | 说明 |
|---------|------|
| `QwenChatModel` | 继承 `BaseChatModel`，兼容 LangChain 标准接口 |
| `api_key` | DashScope API Key |
| `model_name` | 模型名称 (qwen-plus / qwen-max / qwen-turbo) |
| `temperature` | 生成温度，控制随机性，默认 0.7 |
| `max_tokens` | 最大输出 token 数，默认 2048 |
| `_convert_messages()` | 将 LangChain 消息格式 (SystemMessage/HumanMessage/AIMessage) 转为通义千问 API 的 `{"role":..., "content":...}` 格式 |
| `_generate()` | 同步生成方法，调用 DashScope `Generation.call()`，返回 `ChatResult` |
| `_stream()` | 流式生成方法，调用 DashScope `Generation.call(stream=True)`，逐 token 返回 `ChatGeneration` |

#### 5.2.2 `src/agent/core.py` — Agent 核心

| 类/方法 | 说明 |
|---------|------|
| `TCM_SYSTEM_PROMPT` | 常量，中医 Agent 的系统提示词，包含角色设定、辨证体系（八纲/六经/脏腑辨证）、方剂推荐规则、安全免责声明 |
| `create_tcm_agent()` | **核心工厂方法**，创建完整的 LangChain Agent |
| → 创建 `QwenChatModel` | 初始化通义千问 LLM |
| → 加载工具列表 | 从 `tcm_tools.py` 导入 4 个 `@tool` 工具 |
| → 构建 System Prompt | 将 `TCM_SYSTEM_PROMPT` 与 RAG 检索上下文拼接 |
| → 创建 Agent | 使用 `create_tool_calling_agent` 绑定 LLM + 工具 + Prompt |
| → 包装 Executor | 使用 `AgentExecutor` 管理工具调用循环 |
| `get_stream_response()` | 流式对话，使用 `AgentExecutor.astream_events()` 逐 token 输出 |
| `get_response()` | 非流式对话，使用 `AgentExecutor.ainvoke()` 一次性返回 |

---

### 5.3 RAG 层

#### 5.3.1 `src/rag/embedding.py` — 文本向量化

| 类/方法 | 说明 |
|---------|------|
| `TCMEmbedding` | 中医文本向量化器 |
| `model_name` | 默认 `BAAI/bge-small-zh-v1.5`，中文优化，384维向量 |
| `_model` | 懒加载的 `SentenceTransformer` 实例 |
| `embed_documents(texts)` | 批量文本 → 向量列表，用于文档入库 |
| `embed_query(text)` | 单个查询文本 → 向量，用于检索 |

#### 5.3.2 `src/rag/milvus_store.py` — Milvus 向量存储

| 类/方法 | 说明 |
|---------|------|
| `TCMVectorStore` | Milvus 向量数据库管理器 |
| `__init__()` | 初始化连接参数、Embedding 模型、Collection 名称 |
| `connect()` | 建立与 Milvus 的连接 (`connections.connect()`) |
| `create_collection()` | 创建 Collection，定义 Schema（id, text, embedding 384维, source, category），创建 IVF_FLAT 索引 |
| `insert_documents(docs, metadatas)` | 将文档列表向量化后批量插入 Milvus |
| `search(query, top_k)` | 向量相似度搜索，返回 top_k 条最相关文档 |
| `drop_collection()` | 删除 Collection（用于重置数据） |
| `get_collection_stats()` | 获取 Collection 统计信息（文档数等） |

#### 5.3.3 `src/rag/retriever.py` — 检索器

| 类/方法 | 说明 |
|---------|------|
| `TCMRetriever` | 中医知识检索器，组合向量检索 + 关键词匹配 |
| `__init__()` | 初始化 Milvus store + Embedding 模型 |
| `retrieve(query, top_k)` | **核心检索方法**：1) Milvus 向量检索 → 2) 关键词匹配增强 → 3) 融合排序 → 4) 格式化为知识上下文 |
| `_keyword_match(query, docs)` | 在检索结果上做中医关键词（方剂名/药材名/穴位名/症状）二次匹配打分 |
| `_format_context(docs)` | 将检索结果格式化为 LLM 可理解的知识上下文文本 |

---

### 5.4 GraphRAG 层 — `src/graphrag/` (新增)

知识图谱模块，基于 Neo4j 实现中医实体关系建模和多跳推理检索。

#### 5.4.1 `src/graphrag/graph_store.py` — Neo4j 图数据库

| 类/方法 | 说明                                    |
|---------|---------------------------------------|
| `Neo4jGraphStore` | Neo4j 图数据库封装                          |
| `connect()` | 建立 Neo4j 连接 (`bolt://localhost:7687`) |
| `close()` | 关闭连接                                  |
| `execute_query(query, parameters)` | 执行 Cypher 查询，返回结果列表                   |
| `execute_write(query, parameters)` | 执行 Cypher 写操作                         |
| `clear_graph()` | 清空知识图谱                                |
| `get_stats()` | 获取节点数和关系数统计                           |
| `create_constraints()` | 创建唯一性约束（确保节点不重复）                      |

**知识图谱节点类型**：Formula(方剂)、Herb(药材)、Acupoint(穴位)、Constitution(体质)、Symptom(症状)、Meridian(经络)、Category(分类)、Book(出处)、Nature(药性)

**关系类型**：CONTAINS(包含)、TREATS(治疗)、BELONGS_TO(属于)、SOURCE_FROM(出自)、ENTERS_MERIDIAN(归经)、HAS_NATURE(有药性)、HAS_SYMPTOM(有症状)、RECOMMENDS_ACUPOINT(推荐穴位)

#### 5.4.2 `src/graphrag/graph_builder.py` — 知识图谱构建器

| 类/方法 | 说明 |
|---------|------|
| `TCMGraphBuilder` | 从 SQLite 结构化数据构建知识图谱 |
| `build_full_graph()` | **核心方法**：构建完整知识图谱（创建所有节点和关系） |
| `_extract_symptoms(text)` | 从主治文本中提取症状关键词 |
| `_extract_herbs_from_composition(composition)` | 从方剂组成文本中提取药材名 |

#### 5.4.3 `src/graphrag/retriever.py` — 图检索器

| 类/方法 | 说明 |
|---------|------|
| `GraphRetriever` | 知识图谱检索器 |
| `search_entities(keyword, entity_type)` | 搜索实体节点 |
| `get_entity_relations(entity_name, depth)` | 获取实体的关联关系（1度/2度） |
| `find_treatment_path(symptom)` | **核心方法**：根据症状发现治疗路径（症状→方剂/药材/穴位/体质） |
| `find_related_entities(entity_name, relation_type)` | 查找关联实体 |
| `format_context(paths)` | 将检索路径格式化为 LLM 可用的上下文文本 |

#### 5.4.4 `src/graphrag/seed_graph.py` — 知识图谱种子数据

| 内容 | 说明 |
|------|------|
| `init_graph_data()` | 连接 Neo4j → 从 SQLite 加载数据 → 构建知识图谱 → 输出统计 |

---

### 5.5 工具层

所有工具均使用 `@tool` 装饰器注册为 LangChain Tool，Agent 可自动调用。

#### 5.5.1 `src/tools/tcm_tools.py` — 结构化数据查询工具

| 工具函数 | 参数 | 说明 |
|---------|------|------|
| `search_formula()` | `name` (可选, 方剂名), `symptom` (可选, 症状), `category` (可选, 分类) | 查询方剂：支持按名称精确匹配、按症状模糊搜索、按分类筛选 |
| `search_herb()` | `name` (可选), `nature` (可选, 性味), `meridian` (可选, 归经), `effect` (可选, 功效) | 查询药材：支持按名称/性味/归经/功效组合查询 |
| `search_acupoint()` | `name` (可选), `meridian` (可选, 所属经络), `symptom` (可选, 主治症状) | 查询穴位：支持按名称/经络/主治症状查询 |
| `analyze_constitution()` | `symptoms` (必填, 症状列表) | 体质分析：根据用户症状匹配 9 种体质类型，返回体质特征和调理建议 |

所有工具内部调用 `src/data/database.py` 中的 `TCMDatabase` 类进行 SQLite 查询。

#### 5.5.2 `src/tools/graphrag_tools.py` — 知识图谱查询工具 (新增)

| 工具函数 | 参数 | 说明 |
|---------|------|------|
| `SymptomPathTool` (`search_symptom_path`) | `symptom` (必填, 症状关键词) | **GraphRAG 核心工具**：根据症状在知识图谱中查找治疗路径（症状→方剂、症状→药材、症状→穴位、症状→体质、症状→方剂→药材二度路径） |
| `GraphEntitySearchTool` (`search_graph_entity`) | `keyword` (必填), `entity_type` (可选) | 在知识图谱中搜索中医实体节点 |
| `GraphRelationTool` (`search_graph_relation`) | `entity_name` (必填), `depth` (可选, 1或2) | 查询实体的关联关系（支持二度关系） |

所有图谱工具内部调用 `src/graphrag/retriever.py` 中的 `GraphRetriever` 类进行 Neo4j 查询。

---

### 5.6 数据层

#### 5.6.1 `src/data/database.py` — SQLite 数据库

| 类/方法 | 说明 |
|---------|------|
| `TCMDatabase` | SQLite 数据库管理器，单例模式 |
| `__init__(db_path)` | 初始化数据库连接，指定 db 文件路径 |
| `_create_tables()` | 建表：`formulas`(方剂), `herbs`(药材), `acupoints`(穴位), `constitutions`(体质), `chat_history`(对话历史) |
| `add_formula(data)` | 插入一条方剂记录 |
| `search_formulas(name, symptom, category)` | 查询方剂：支持 LIKE 模糊匹配 |
| `add_herb(data)` | 插入一条药材记录 |
| `search_herbs(name, nature, meridian, effect)` | 查询药材：支持多字段 LIKE 匹配 |
| `add_acupoint(data)` | 插入一条穴位记录 |
| `search_acupoints(name, meridian, symptom)` | 查询穴位：支持模糊匹配 |
| `add_constitution(data)` | 插入一条体质记录 |
| `get_constitution_by_symptoms(symptoms)` | 根据症状关键词匹配体质类型 |
| `get_all_formulas()` / `get_all_herbs()` / `get_all_acupoints()` / `get_all_constitutions()` | 获取全部记录的列表 |
| `save_chat_message(role, content)` | 保存对话历史 |
| `get_chat_history(limit)` | 获取最近 N 条对话记录 |

#### 5.5.2 `src/data/seed.py` — 种子数据初始化

| 内容 | 说明 |
|------|------|
| `FORMULAS` | 10 首经典方剂数据：麻黄汤、桂枝汤、小柴胡汤、四君子汤、四物汤、六味地黄丸、逍遥散、银翘散、藿香正气散、温胆汤 |
| `HERBS` | 10 味常用药材：麻黄、桂枝、柴胡、人参、当归、熟地黄、茯苓、金银花、藿香、半夏 |
| `ACUPOINTS` | 8 个常用穴位：合谷、足三里、三阴交、百会、风池、关元、内关、太冲 |
| `CONSTITUTIONS` | 5 种体质类型：平和质、气虚质、阳虚质、阴虚质、痰湿质 |
| `init_seed_data()` | 主函数：连接 SQLite → 插入方剂/药材/穴位/体质数据 → 连接 Milvus → 将中医经典知识段落向量化入库 |

---

### 5.6 API 层 — `src/api/server.py`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 根路径，返回服务信息 |
| `/chat` | POST | 普通对话接口，请求体 `{"message": "...", "session_id": "..."}`，返回完整 JSON 响应 |
| `/chat/stream` | POST | 流式对话接口 (SSE)，逐 token 推送，`Content-Type: text/event-stream` |
| `/health` | GET | 健康检查接口 |
| `/tools` | GET | 列出所有可用工具及其描述 |

| 类/模型 | 说明 |
|---------|------|
| `ChatRequest` | 请求体 Pydantic 模型：`message`(str), `session_id`(Optional[str]) |
| `ChatResponse` | 响应体 Pydantic 模型：`reply`(str), `session_id`(str), `tools_used`(List[str]) |
| `app` | FastAPI 应用实例，配置 CORS 中间件 |
| `session_store` | 内存字典，`session_id → 对话历史列表`，简易会话管理 |
| `chat_endpoint()` | `/chat` 处理函数：创建 Agent → 执行 → 保存历史 → 返回响应 |
| `chat_stream_endpoint()` | `/chat/stream` 处理函数：创建 Agent → 流式执行 → SSE 推送 |

---

### 5.7 部署层

#### 5.7.1 `Dockerfile`

采用**多阶段构建 + uv**，分为两个阶段：

| 阶段 | 说明 |
|------|------|
| **builder** | 基于 `python:3.13-slim`，安装 uv，复制项目文件，执行 `uv sync --frozen --no-dev` |
| **runtime** | 基于 `python:3.13-slim`，从 builder 复制 `.venv` 和源码，创建非 root 用户 `appuser`，暴露 8000 端口 |

关键优化：
- `UV_COMPILE_BYTECODE=1` → 预编译 .pyc
- `UV_LINK_MODE=copy` → 不使用软链接，方便 COPY
- `--mount=type=cache` → 缓存 uv 下载，加速重复构建

#### 5.7.2 `docker-compose.yml`

编排 4 个服务：

| 服务 | 镜像 | 端口          | 说明 |
|------|------|-------------|------|
| `etcd` | `quay.io/coreos/etcd:v3.5.5` | 2379-2380   | Milvus 元数据存储 |
| `minio` | `minio/minio:latest` | 9000-9001   | Milvus 对象存储 |
| `milvus` | `milvusdb/milvus:v2.4.0` | 19530, 9091 | 向量数据库 |
| `neo4j` | `neo4j:5.26.0` | 7474, 7687  | 图数据库 |
| `agent` | 本地构建 | 8000        | 中医 AI Agent 服务 |

依赖链：`agent` 依赖 `milvus` + `neo4j`，`milvus` 依赖 `etcd` + `minio`。

---

## 六、数据流图

```
┌──────────┐     POST /chat      ┌──────────┐
│  客户端    │ ──────────────────► │ FastAPI   │
│ (浏览器/   │ ◄────────────────── │  Server   │
│  App/API)  │     JSON/SSE       └────┬─────┘
└──────────┘                           │
                                       │ create_tcm_agent()
                                       ▼
                              ┌─────────────────┐
                              │  LangChain       │
                              │  AgentExecutor   │
                              └────────┬────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
            ┌───────────┐    ┌─────────────┐    ┌──────────────┐
            │ Qwen LLM  │    │  TCM Tools   │    │ TCMRetriever │
            │ (DashScope)│    │  (4 tools)   │    │  (RAG)       │
            └───────────┘    └──────┬──────┘    └──────┬───────┘
                                    │                  │
                                    ▼                  ▼
                            ┌─────────────┐    ┌──────────────┐
                            │   SQLite    │    │   Milvus     │
                            │  (tcm.db)   │    │  (向量库)     │
                            └─────────────┘    └──────────────┘
```

---

## 七、关键技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 框架 | LangChain | 成熟的工具调用链、丰富的集成生态 |
| LLM | 通义千问 (qwen-plus) | 中文能力强、DashScope API 稳定、性价比高 |
| 向量数据库 | Milvus | 生产级、支持十亿级向量、Docker 部署方便 |
| 图数据库 | Neo4j | 知识图谱标准工具、Cypher 查询语言灵活、Docker 部署方便 |
| 结构化数据 | SQLite | 轻量零配置、方剂/药材数据量不大、单文件便于备份 |
| 嵌入模型 | BAAI/bge-small-zh-v1.5 | 中文优化、384维小而快、开源免费 |
| Web 框架 | FastAPI | 异步高性能、自动生成 API 文档、类型安全 |
| 包管理 | uv | 极速安装、锁文件保证可复现、Docker 友好 |
| 部署 | Docker + docker-compose | 一键启动 Milvus + Neo4j + Agent、环境隔离 |

---

## 八、开发指南

### 环境准备

```bash
# 1. 克隆项目
cd E:\agent\zhongyi_ai

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY

# 3. 安装依赖
uv sync

# 4. 初始化数据
uv run python -m src.data.seed

# 5. 初始化知识图谱（需先启动 Neo4j）
docker-compose up -d neo4j
uv run python -m src.graphrag.seed_graph

# 6. 启动服务
uv run python -m src.api.server
```

### 添加新工具

1. 在 `src/tools/tcm_tools.py` 中添加新的 `@tool` 函数
2. 函数内部调用 `src/data/database.py` 的查询方法
3. 如需新数据表，在 `database.py` 的 `_create_tables()` 中添加建表语句
4. 工具会被 `core.py` 中的 `create_tcm_agent()` 自动加载

### 添加新知识到 RAG

1. 在 `src/data/seed.py` 中添加新的知识文本
2. 运行 `uv run python -m src.data.seed` 重新入库
3. 文本会被向量化并存入 Milvus

### 添加新知识到知识图谱

1. 在 `src/data/seed.py` 中添加新的方剂/药材/穴位/体质数据
2. 运行 `uv run python -m src.data.seed` 更新 SQLite
3. 运行 `uv run python -m src.graphrag.seed_graph` 重建知识图谱
4. 新的实体和关系会自动从 SQLite 数据提取并写入 Neo4j

### 调整模型

编辑 `.env`：
```
QWEN_MODEL=qwen-max    # 更强的模型
QWEN_MODEL=qwen-turbo  # 更快更便宜
```

---

## 九、安全注意事项

1. **医疗免责声明**：所有回答附带"仅供参考，不能替代专业医师诊断"
2. **急重症识别**：System Prompt 中包含急重症关键词识别，强制建议就医
3. **剂量安全**：涉及具体克数时强调"请在医师指导下使用"
4. **毒性药材**：对附子、乌头等有毒药材标注毒性并警告
5. **API Key 保护**：`.env` 已加入 `.gitignore`，不提交到版本控制
