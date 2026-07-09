# 中医 AI Agent

基于 **LangChain + 通义千问 + Milvus + Neo4j + SQLite** 的中医智能助手。

## 技术栈

| 组件 | 技术 |
|------|------|
| Agent 框架 | LangChain |
| LLM | 通义千问 (qwen-plus) |
| 向量数据库 | Milvus |
| 图数据库 | Neo4j (知识图谱) |
| 结构化数据 | SQLite |
| API 框架 | FastAPI |
| 部署 | Docker + uv |

## 项目结构

```
zhongyi_ai/
├── src/
│   ├── agent/          # Agent 核心 (LLM + Prompt + Agent)
│   │   ├── llm.py      # 通义千问封装
│   │   └── core.py     # Agent 创建和执行
│   ├── rag/            # RAG 检索增强
│   │   ├── embedding.py    # 文本向量化
│   │   ├── milvus_store.py # Milvus 向量存储
│   │   └── retriever.py    # 检索器
│   ├── graphrag/       # GraphRAG 知识图谱 (新增)
│   │   ├── graph_store.py  # Neo4j 图数据库
│   │   ├── graph_builder.py # 知识图谱构建
│   │   ├── retriever.py     # 图检索器
│   │   └── seed_graph.py    # 图谱种子数据
│   ├── tools/          # LangChain 工具
│   │   ├── tcm_tools.py     # 方剂/药材/穴位/体质查询
│   │   └── graphrag_tools.py # 知识图谱查询工具 (新增)
│   ├── data/           # 数据层
│   │   ├── database.py # SQLite 操作
│   │   └── seed.py     # 种子数据
│   ├── api/            # API 服务
│   │   └── server.py   # FastAPI
│   └── config.py       # 配置管理
├── data/               # 数据文件 (SQLite)
├── scripts/            # 启动脚本
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## 快速开始

### 1. 配置环境

```bash
cp .env.example .env
# 编辑 .env，填入你的通义千问 API Key
```

### 2. 安装依赖

```bash
uv sync
```

### 3. 初始化数据

```bash
uv run python -m src.data.seed
```

### 4. 启动服务

**本地开发：**
```bash
# Linux/Mac
bash scripts/start.sh

# Windows
scripts\start.bat
```

**Docker 部署：**
```bash
docker-compose up -d
```

### 5. 访问 API

- API 地址: http://localhost:8000
- API 文档: http://localhost:8000/docs

## API 接口

### POST /chat — 对话

```json
{
  "message": "我最近总是疲劳乏力，食欲不振，是什么问题？",
  "stream": false
}
```

### POST /chat/stream — 流式对话

同上，`stream: true`。

### GET /health — 健康检查

## 功能

1. **辨证论治** — 根据症状进行中医辨证分析
2. **方剂查询** — 查询经典方剂的组成、功效、适应症
3. **药材查询** — 查询中药材的性味归经、用法禁忌
4. **穴位推荐** — 根据症状推荐合适穴位
5. **体质辨识** — 九种体质判断和调理建议
6. **RAG 增强** — 基于中医经典知识库的检索增强
7. **知识图谱推理** — 通过 Neo4j 发现症状→方剂→药材等多跳关联路径 (新增)
