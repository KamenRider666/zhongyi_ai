# Linux 环境搭建指南

> 适用系统：Ubuntu 22.04 / Ubuntu 20.04  
> 部署方式：Docker Compose  
> 目标：在一台 Linux 服务器上搭建 MySQL、Neo4j、Qdrant、LangFuse 四个基础服务，并部署运行中医 AI Agent 项目

---

## 目录

- [0. 前置准备](#0-前置准备)
- [1. MySQL](#1-mysql)
- [2. Neo4j](#2-neo4j)
- [3. Qdrant](#3-qdrant)
- [4. LangFuse](#4-langfuse)
- [5. 统一 docker-compose](#5-统一-docker-compose)
- [6. 防火墙配置](#6-防火墙配置)
- [7. 服务验证](#7-服务验证)
- [8. 连接信息汇总](#8-连接信息汇总)
- [9. 项目运行环境](#9-项目运行环境)
- [10. 数据导入](#10-数据导入)
- [11. 启动项目](#11-启动项目)

---

## 0. 前置准备

### 0.1 安装 Docker

```bash
# 卸载旧版本（如果有）
sudo apt-get remove docker docker-engine docker.io containerd runc

# 安装依赖
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# 添加 Docker GPG 密钥
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 添加 Docker 源
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

### 0.2 验证安装

```bash
docker --version           # Docker version 24.x.x
docker compose version     # Docker Compose version v2.x.x
```

### 0.3 配置 Docker 镜像加速（国内推荐）

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": ["https://mirror.ccs.tencentyun.com"]
}
EOF
sudo systemctl daemon-reload && sudo systemctl restart docker
```

### 0.4 创建项目目录

```bash
mkdir -p ~/tcm-services && cd ~/tcm-services
mkdir -p mysql_data neo4j_data qdrant_data langfuse_data
```

### 0.5 安装 Python 3.11+

项目要求 Python 3.11 或更高版本。

```bash
# 检查是否已安装（Ubuntu 22.04 默认 3.10，不够）
python3 --version

# 如果 < 3.11，安装 3.12
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev

# 验证
python3.12 --version
```

### 0.6 安装 uv 包管理器

项目使用 [uv](https://github.com/astral-sh/uv) 管理依赖，比 pip 快 10 倍以上。

```bash
# 安装 uv（Linux/macOS）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 重新加载 shell 环境
source ~/.bashrc

# 验证
uv --version
```

### 0.7 获取通义千问 API Key

1. 打开 [阿里云百炼平台](https://bailian.console.aliyun.com/)
2. 登录或注册阿里云账号
3. 进入 **模型广场 → API-KEY 管理**
4. 创建一个新的 API Key，复制保存

> 项目同时使用 DashScope API 做 **LLM 对话** 和 **Embedding 向量化**，所以一个 Key 即可。

### 0.8 配置 .env 文件

在项目根目录创建 `.env` 文件（参考第 8 节的模板）：

```bash
cd ~/tcm-services/zhongyi-ai

cat > .env << 'EOF'
# === 通义千问 ===
DASHSCOPE_API_KEY=sk-你的真实Key
QWEN_MODEL=qwen-plus

# === MySQL ===
DB_TYPE=mysql
MYSQL_HOST=<服务器IP>
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=dcdevtest
MYSQL_DATABASE=agenttest

# === Neo4j ===
NEO4J_URI=bolt://<服务器IP>:7644
NEO4J_USER=neo4j
NEO4J_PASSWORD=zhongyi_neo4j_2026

# === Qdrant ===
QDRANT_HOST=<服务器IP>
QDRANT_PORT=7645
QDRANT_COLLECTION=zhongyi-qdrant

# === LangFuse（可选）===
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxxxxxxx
LANGFUSE_HOST=http://<服务器IP>:3000
EOF
```

---

## 9. 项目运行环境

### 9.1 克隆项目并安装依赖

```bash
# 克隆代码（如果还没有）
cd ~/tcm-services
git clone <项目仓库地址> zhongyi-ai
cd zhongyi-ai

# 安装所有 Python 依赖
uv sync
```

### 9.2 依赖关系说明

启动项目前，需确保以下服务已运行：

| 服务 | 必需/可选 | 不运行的影响 |
|------|----------|-------------|
| Qdrant | **必需** | 向量检索不可用，Agent 无法查知识库 |
| Neo4j | **必需** | 知识图谱不可用，无法查询药材-症状关系 |
| MySQL | 可选 | 可回退 SQLite，但多轮对话历史会丢失 |
| LangFuse | 可选 | 仅影响 LLM 调用追踪，不影响核心功能 |

---

## 10. 数据导入

服务搭好后，需要把中药知识导入 Qdrant 向量库。

### 10.1 导入全部数据

```bash
cd ~/tcm-services/zhongyi-ai
uv run python scripts/import_to_qdrant.py
```

### 10.2 导入选项

```bash
# 只导入指定文件
uv run python scripts/import_to_qdrant.py --file herbs.jsonl

# 清空集合后重新导入
uv run python scripts/import_to_qdrant.py --reset

# 查看所有参数
uv run python scripts/import_to_qdrant.py --help
```

### 10.3 数据文件

| 文件 | 内容 | 条数 |
|------|------|------|
| `data/herbs.jsonl` | 中药材 | ~3000 |
| `data/formulas_test.jsonl` | 方剂 | ~300 |
| `data/diseases_test.jsonl` | 疾病 | ~1000 |
| `data/syndromes_test.jsonl` | 证型 | ~500 |

### 10.4 初始化知识图谱（Neo4j）

```bash
uv run python -m src.graphrag.seed_graph
```

> 此命令会将药材、症状、方剂等关系写入 Neo4j。需 Neo4j 已启动。

### 10.5 初始化 MySQL 表结构

```bash
uv run python -m src.data.seed
```

---

## 11. 启动项目

### 11.1 开发模式启动

```bash
cd ~/tcm-services/zhongyi-ai
uv run python -m src.api.server
```

服务启动后：
- **对话界面**：`http://<服务器IP>:8000`
- **API 文档**：`http://<服务器IP>:8000/docs`

### 11.2 一键启动脚本

项目自带 `scripts/start.sh`，会自动检查环境、初始化数据、启动服务：

```bash
cd ~/tcm-services/zhongyi-ai
bash scripts/start.sh
```

### 11.3 使用 systemd 设为开机自启

创建 systemd 服务文件：

```bash
sudo tee /etc/systemd/system/zhongyi-ai.service << 'EOF'
[Unit]
Description=中医 AI Agent 服务
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/tcm-services/zhongyi-ai
Environment="PATH=/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/ubuntu/.local/bin/uv run python -m src.api.server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启用并启动
sudo systemctl daemon-reload
sudo systemctl enable zhongyi-ai
sudo systemctl start zhongyi-ai

# 查看状态
sudo systemctl status zhongyi-ai
```

> **注意**：把 `User`、`WorkingDirectory`、`ExecStart` 中的路径替换为实际值。

> 把 `<服务器IP>` 替换为实际 IP，API Key 替换为真实值。

---

## 1. MySQL

### 1.1 版本说明

| 项 | 值 |
|----|-----|
| 镜像 | `mysql:8.0` |
| 端口 | `3306` |
| 数据库名 | `agenttest` |
| 用户名 | `root` |
| 密码 | `dcdevtest` |

### 1.2 启动命令

```bash
docker run -d \
  --name mysql-tcm \
  --restart unless-stopped \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=dcdevtest \
  -e MYSQL_DATABASE=agenttest \
  -e MYSQL_CHARACTER_SET_SERVER=utf8mb4 \
  -e MYSQL_COLLATION_SERVER=utf8mb4_unicode_ci \
  -v $(pwd)/mysql_data:/var/lib/mysql \
  mysql:8.0
```

### 1.3 验证

```bash
docker exec -it mysql-tcm mysql -uroot -pdcdevtest -e "SHOW DATABASES;"
```

---

## 2. Neo4j

### 2.1 版本说明

| 项 | 值                    |
|----|----------------------|
| 镜像 | `neo4j:5.26.0`                     |
| Bolt 端口 | `7644` (映射容器内 `7687`)    |
| HTTP 端口 | `7474`               |
| 用户名 | `neo4j`              |
| 密码 | `zhongyi_neo4j_2026` |

### 2.2 启动命令

```bash
docker run -d \
  --name neo4j-tcm \
  --restart unless-stopped \
  -p 7474:7474 \
  -p 7644:7687 \
  -e NEO4J_AUTH=neo4j/zhongyi_neo4j_2026 \
  -e NEO4J_PLUGINS='["apoc"]' \
  -e NEO4J_server_memory_heap_initial__size=512m \
  -e NEO4J_server_memory_heap_max__size=1G \
  -v $(pwd)/neo4j_data/data:/data \
  -v $(pwd)/neo4j_data/logs:/logs \
  neo4j:5.26.0
```

### 2.3 验证

浏览器访问 `http://<服务器IP>:7474`，用 `neo4j / zhongyi_neo4j_2026` 登录。

---

## 3. Qdrant

### 3.1 版本说明

| 项 | 值 |
|----|-----|
| 镜像 | `qdrant/qdrant:latest` |
| HTTP 端口 | `7645` (映射容器内 `6333`) |
| gRPC 端口 | `6334` |
| Collection | `zhongyi-qdrant` |

### 3.2 启动命令

```bash
docker run -d \
  --name qdrant-tcm \
  --restart unless-stopped \
  -p 7645:6333 \
  -p 6334:6334 \
  -v $(pwd)/qdrant_data:/qdrant/storage \
  qdrant/qdrant:latest
```

### 3.3 验证

```bash
# 检查服务状态
curl http://localhost:7645/health

# 检查 collections
curl http://localhost:7645/collections
```

---

## 4. LangFuse

### 4.1 版本说明

| 组件 | 镜像 | 端口 |
|------|------|------|
| PostgreSQL | `postgres:15` | `5433` |
| LangFuse Server | `langfuse/langfuse:2` | `3000` |
| LangFuse Worker | `langfuse/langfuse-worker:2` | — |

### 4.2 创建 compose 文件

```bash
cd ~/tcm-services
```

```bash
cat > docker-compose.langfuse.yml << 'EOF'
services:
  langfuse-db:
    image: postgres:15
    container_name: langfuse-db
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse
      POSTGRES_DB: langfuse
    volumes:
      - ./langfuse_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U langfuse"]
      interval: 5s
      timeout: 5s
      retries: 5

  langfuse-server:
    image: langfuse/langfuse:2
    container_name: langfuse-server
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      NEXTAUTH_SECRET: my-random-secret-string-for-langfuse
      NEXTAUTH_URL: http://<服务器IP>:3000
      TELEMETRY_ENABLED: "false"
    ports:
      - "3000:3000"
    depends_on:
      langfuse-db:
        condition: service_healthy
    restart: unless-stopped

  langfuse-worker:
    image: langfuse/langfuse-worker:2
    container_name: langfuse-worker
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
    depends_on:
      langfuse-db:
        condition: service_healthy
    restart: unless-stopped
EOF
```

> **注意**：把 `NEXTAUTH_URL` 里的 `<服务器IP>` 替换为实际 IP，`NEXTAUTH_SECRET` 替换为一个随机字符串。

### 4.3 启动

```bash
docker compose -f docker-compose.langfuse.yml up -d
```

### 4.4 创建项目和获取密钥

1. 浏览器打开 `http://<服务器IP>:3000`
2. 首次访问会自动跳转到注册页面，点击 **Sign up** 创建管理员账号
3. 登录后，创建新项目，名称填 `zhongyi-ai`
4. 记下项目页显示的 **Public Key** 和 **Secret Key**（`pk-lf-...` / `sk-lf-...`）

### 4.5 验证

```bash
docker compose -f docker-compose.langfuse.yml ps
# 三个容器状态均为 Up
```

---

## 5. 统一 docker-compose

如果你希望用**一个 compose 文件管理所有服务**，可以使用以下配置：

```bash
cat > docker-compose.all.yml << 'EOF'
services:
  # ==================== MySQL ====================
  mysql:
    image: mysql:8.0
    container_name: mysql-tcm
    restart: unless-stopped
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: dcdevtest
      MYSQL_DATABASE: agenttest
      MYSQL_CHARACTER_SET_SERVER: utf8mb4
      MYSQL_COLLATION_SERVER: utf8mb4_unicode_ci
    volumes:
      - ./mysql_data:/var/lib/mysql

  # ==================== Neo4j ====================
  neo4j:
    image: neo4j:5.26.0
    container_name: neo4j-tcm
    restart: unless-stopped
    ports:
      - "7474:7474"
      - "7644:7687"
    environment:
      NEO4J_AUTH: neo4j/zhongyi_neo4j_2026
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_server_memory_heap_initial__size: 512m
      NEO4J_server_memory_heap_max__size: 1G
    volumes:
      - ./neo4j_data/data:/data
      - ./neo4j_data/logs:/logs

  # ==================== Qdrant ====================
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant-tcm
    restart: unless-stopped
    ports:
      - "7645:6333"
      - "6334:6334"
    volumes:
      - ./qdrant_data:/qdrant/storage

  # ==================== LangFuse ====================
  langfuse-db:
    image: postgres:15
    container_name: langfuse-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse
      POSTGRES_DB: langfuse
    volumes:
      - ./langfuse_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U langfuse"]
      interval: 5s
      timeout: 5s
      retries: 5

  langfuse-server:
    image: langfuse/langfuse:2
    container_name: langfuse-server
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      NEXTAUTH_SECRET: my-random-secret-string-for-langfuse
      NEXTAUTH_URL: http://<服务器IP>:3000
      TELEMETRY_ENABLED: "false"
    ports:
      - "3000:3000"
    depends_on:
      langfuse-db:
        condition: service_healthy

  langfuse-worker:
    image: langfuse/langfuse-worker:2
    container_name: langfuse-worker
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
    depends_on:
      langfuse-db:
        condition: service_healthy
EOF

# 一键启动所有服务
docker compose -f docker-compose.all.yml up -d
```

---

## 6. 防火墙配置

如果服务器开启了防火墙（UFW），需要开放对应端口：

```bash
# MySQL
sudo ufw allow 3306/tcp

# Neo4j
sudo ufw allow 7474/tcp   # HTTP 管理界面
sudo ufw allow 7644/tcp   # Bolt 协议

# Qdrant
sudo ufw allow 7645/tcp   # HTTP API
sudo ufw allow 6334/tcp   # gRPC

# LangFuse
sudo ufw allow 3000/tcp   # Web UI

# 重新加载防火墙
sudo ufw reload
```

> 如果使用云服务商（阿里云/腾讯云等），还需要在**安全组**中添加对应的入站规则。

---

## 7. 服务验证

### 7.1 MySQL

```bash
docker exec -it mysql-tcm mysql -uroot -pdcdevtest -e "SELECT VERSION();"
# 应输出: 8.0.x
```

### 7.2 Neo4j

```bash
curl -s http://localhost:7474 | head -5
# 应返回 JSON 格式的 Neo4j 信息
```

### 7.3 Qdrant

```bash
curl -s http://localhost:7645/health
# 应返回: {"title":"qdrant - vector search engine","version":"..."}
```

### 7.4 LangFuse

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
# 应返回: 200
```

### 7.5 所有容器状态

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

---

## 8. 连接信息汇总

| 服务 | 地址 | 端口 | 用户名 | 密码 |
|------|------|------|--------|------|
| MySQL | `<服务器IP>` | 3306 | root | dcdevtest |
| Neo4j Bolt | `<服务器IP>` | 7644 | neo4j | zhongyi_neo4j_2026 |
| Neo4j HTTP | `<服务器IP>` | 7474 | neo4j | zhongyi_neo4j_2026 |
| Qdrant HTTP | `<服务器IP>` | 7645 | — | — |
| Qdrant gRPC | `<服务器IP>` | 6334 | — | — |
| LangFuse UI | `<服务器IP>` | 3000 | 登录邮箱 | 登录密码 |

### 开发机 `.env` 配置示例

```env
# === 通义千问 ===
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
QWEN_MODEL=qwen-plus

# === MySQL ===
DB_TYPE=mysql
MYSQL_HOST=<服务器IP>
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=dcdevtest
MYSQL_DATABASE=agenttest

# === Neo4j ===
NEO4J_URI=bolt://<服务器IP>:7644
NEO4J_USER=neo4j
NEO4J_PASSWORD=zhongyi_neo4j_2026

# === Qdrant ===
QDRANT_HOST=<服务器IP>
QDRANT_PORT=7645
QDRANT_COLLECTION=zhongyi-qdrant

# === LangFuse ===
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxxxxxxx
LANGFUSE_HOST=http://<服务器IP>:3000
```
