# Linux 环境搭建指南（CentOS 版）

> 适用系统：CentOS 7 / CentOS Stream 8 / CentOS Stream 9 / Rocky Linux 8/9 / AlmaLinux 8/9  
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

### 0.1 系统版本确认

```bash
# 查看 CentOS 版本
cat /etc/redhat-release
# CentOS Linux release 7.9.2009 / CentOS Stream release 8 / CentOS Stream release 9

# 查看内核版本
uname -r
```

> **说明**：Docker 要求内核版本 3.10+，CentOS 7 默认满足。  
> 本文命令同时兼容 `yum`（CentOS 7）和 `dnf`（CentOS Stream 8/9），CentOS 8+ 下 `yum` 是 `dnf` 的软链接，二者等价。

### 0.2 安装 Docker

#### CentOS 7

```bash
# 卸载旧版本（如果有）
sudo yum remove -y docker \
                  docker-client \
                  docker-client-latest \
                  docker-common \
                  docker-latest \
                  docker-latest-logrotate \
                  docker-logrotate \
                  docker-engine

# 安装 yum-utils（提供 yum-config-manager）
sudo yum install -y yum-utils device-mapper-persistent-data lvm2

# 添加 Docker 官方源（国内可用阿里云镜像加速）
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
# 国内推荐替换为阿里云源：
# sudo yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo

# 安装 Docker
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

#### CentOS Stream 8/9 / Rocky / AlmaLinux

```bash
# 卸载旧版本（podman/buildah 可能与 docker 冲突）
sudo dnf remove -y docker docker-client docker-client-latest docker-common \
                   docker-latest docker-latest-logrotate docker-logrotate docker-engine \
                   podman runc buildah

# 添加 Docker 官方源
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
# 国内推荐替换为阿里云源：
# sudo dnf config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo

# 安装 Docker
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

### 0.3 启动并设置开机自启

```bash
sudo systemctl start docker
sudo systemctl enable docker

# 验证
docker --version           # Docker version 24.x.x
docker compose version     # Docker Compose version v2.x.x
sudo docker run hello-world
```

> **注意**：CentOS 7 上如果遇到 `iptables: No chain/target/match by that name` 错误，请重启 Docker：`sudo systemctl restart docker`。

### 0.4 配置 Docker 镜像加速（国内推荐）

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://docker.m.daocloud.io"
  ]
}
EOF
sudo systemctl daemon-reload && sudo systemctl restart docker
```

### 0.5 创建项目目录

```bash
mkdir -p ~/tcm-services && cd ~/tcm-services
mkdir -p mysql_data neo4j_data qdrant_data langfuse_data
```

### 0.6 安装 Python 3.11+

项目要求 Python 3.11 或更高版本。CentOS 7 默认 Python 2.7，CentOS Stream 8 默认 Python 3.6，CentOS Stream 9 默认 Python 3.9，**均不满足要求**，需手动安装。

#### 方式一：使用 SCL 软件集（CentOS 7）

```bash
# 安装 SCL 源
sudo yum install -y centos-release-scl

# 安装 Python 3.11（rh-python311）
sudo yum install -y rh-python311 rh-python311-python-devel rh-python311-python-pip

# 启用 SCL（每次新开 shell 都要执行，或加入 ~/.bashrc）
scl enable rh-python311 bash

# 验证
python3 --version   # Python 3.11.x
```

> 永久启用，写入 `~/.bashrc`：
> ```bash
> echo 'source /opt/rh/rh-python311/enable' >> ~/.bashrc
> source ~/.bashrc
> ```

#### 方式二：使用 dnf 模块（CentOS Stream 8/9 / Rocky / Alma）

```bash
# CentOS Stream 9 / Rocky 9 / Alma 9 默认仓库已有 Python 3.11/3.12
sudo dnf install -y python3.11 python3.11-devel python3.11-pip

# 或者启用 stream 模块（8 系列）
sudo dnf module reset -y python36
sudo dnf module enable -y python39
sudo dnf install -y python39 python39-devel

# 验证
python3.11 --version   # CentOS 9/Rocky 9/Alma 9
# 或
python3.9 --version    # CentOS 8/Rocky 8/Alma 8（再通过下面 uv 装新版）
```

#### 方式三：通过 uv 安装指定版本（通用推荐）

如果系统 Python 版本不够（如 CentOS 7 的 SCL 无法用），可让 `uv` 自行下载管理 Python：

```bash
# 先用系统已有 Python 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# uv 会自动下载并管理 Python 3.11/3.12
uv python install 3.12
uv python list
```

> 项目 `uv sync` 时会自动选择合适的 Python 版本，无需手动 `python3 --version` 满足。

### 0.7 安装构建依赖

部分 Python 包（如 `mysqlclient`、`lxml`）需要编译，CentOS 需安装编译工具：

```bash
# CentOS 7
sudo yum groupinstall -y "Development Tools"
sudo yum install -y gcc gcc-c++ make openssl-devel bzip2-devel libffi-devel zlib-devel

# CentOS Stream 8/9
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y gcc gcc-c++ make openssl-devel bzip2-devel libffi-devel zlib-devel
```

### 0.8 安装 Git

```bash
sudo yum install -y git     # CentOS 7
sudo dnf install -y git     # CentOS 8/9

git --version
```

### 0.9 安装 uv 包管理器

项目使用 [uv](https://github.com/astral-sh/uv) 管理依赖，比 pip 快 10 倍以上。

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 重新加载 shell 环境
source ~/.bashrc

# 验证
uv --version
```

### 0.10 获取通义千问 API Key

1. 打开 [阿里云百炼平台](https://bailian.console.aliyun.com/)
2. 登录或注册阿里云账号
3. 进入 **模型广场 → API-KEY 管理**
4. 创建一个新的 API Key，复制保存

> 项目同时使用 DashScope API 做 **LLM 对话** 和 **Embedding 向量化**，所以一个 Key 即可。

### 0.11 关闭 SELinux（避免 Docker 挂载权限问题）

CentOS 默认开启 SELinux，可能导致 Docker 容器无法访问挂载目录。推荐临时关闭或设为宽松模式：

```bash
# 查看当前状态
getenforce

# 临时关闭（重启后失效）
sudo setenforce 0

# 永久关闭（需重启生效）
sudo sed -i 's/^SELINUX=enforcing$/SELINUX=disabled/' /etc/selinux/config
# 或设为宽松模式：
# sudo sed -i 's/^SELINUX=enforcing$/SELINUX=permissive/' /etc/selinux/config
```

> **替代方案**：若不愿关闭 SELinux，可在 docker run 时给挂载目录加 `:z` 或 `:Z` 后缀自动调整标签，例如 `-v $(pwd)/mysql_data:/var/lib/mysql:z`。

### 0.12 配置 .env 文件

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
# 获取当前用户名和家目录
CURRENT_USER=$(whoami)
HOME_DIR=$(echo ~$CURRENT_USER)

sudo tee /etc/systemd/system/zhongyi-ai.service << EOF
[Unit]
Description=中医 AI Agent 服务
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${HOME_DIR}/tcm-services/zhongyi-ai
Environment="PATH=${HOME_DIR}/.local/bin:${HOME_DIR}/.cargo/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=${HOME_DIR}/.local/bin/uv run python -m src.api.server
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

> **注意**：
> - 上述脚本会自动用当前用户名和家目录生成配置，无需手动替换。
> - 若 `uv` 安装在 `~/.cargo/bin`（新版默认），`PATH` 已包含；若在 `~/.local/bin`，也包含在内。
> - 如果用了 SCL Python，还需在 `Environment` 中加 `source /opt/rh/rh-python311/enable` 的等效配置，建议改用 `uv` 管理 Python 以避免此问题。

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

> **SELinux 提示**：若未关闭 SELinux 且挂载目录报权限错误，把挂载项改为 `-v $(pwd)/mysql_data:/var/lib/mysql:z`。

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

> **SELinux 提示**：若未关闭 SELinux 且卷挂载报权限错误，可在每个 `volumes` 挂载项后加 `:z`，例如 `- ./mysql_data:/var/lib/mysql:z`。统一 compose 方式下也可全局临时关闭 SELinux（见 0.11）。

---

## 6. 防火墙配置

CentOS 默认使用 `firewalld`（不是 Ubuntu 的 `ufw`）。

### 6.1 查看防火墙状态

```bash
sudo systemctl status firewalld
sudo firewall-cmd --state
```

> 若未启用：`sudo systemctl start firewalld && sudo systemctl enable firewalld`

### 6.2 开放端口

```bash
# MySQL
sudo firewall-cmd --permanent --add-port=3306/tcp

# Neo4j
sudo firewall-cmd --permanent --add-port=7474/tcp   # HTTP 管理界面
sudo firewall-cmd --permanent --add-port=7644/tcp   # Bolt 协议

# Qdrant
sudo firewall-cmd --permanent --add-port=7645/tcp   # HTTP API
sudo firewall-cmd --permanent --add-port=6334/tcp   # gRPC

# LangFuse
sudo firewall-cmd --permanent --add-port=3000/tcp   # Web UI

# 项目服务
sudo firewall-cmd --permanent --add-port=8000/tcp   # FastAPI 对话界面

# 重新加载防火墙（使配置生效）
sudo firewall-cmd --reload

# 查看已开放端口
sudo firewall-cmd --list-ports
```

### 6.3 若使用 iptables（部分精简版系统）

```bash
sudo iptables -I INPUT -p tcp -m multiport --dports 3306,7474,7644,7645,6334,3000,8000 -j ACCEPT
sudo service iptables save   # CentOS 7
# 或
sudo iptables-save | sudo tee /etc/sysconfig/iptables
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

---

## 附录：CentOS 与 Ubuntu 差异速查表

| 维度 | Ubuntu | CentOS |
|------|--------|--------|
| 包管理器 | `apt-get` | `yum` / `dnf` |
| Docker 源 | `download.docker.com/linux/ubuntu` | `download.docker.com/linux/centos` |
| 防火墙 | `ufw` | `firewalld`（`firewall-cmd`） |
| SELinux | 默认关闭 | 默认 enforcing，建议关闭或加 `:z` |
| 默认 Python | 22.04: 3.10 | 7: 2.7 / Stream8: 3.6 / Stream9: 3.9 |
| Python 3.11+ 安装 | `apt install python3.12` | SCL（7）/ dnf 模块（8/9）/ uv 管理 |
| 默认用户 | `ubuntu` | `centos` / `root` / `ec2-user` |
| 编译工具组 | `build-essential` | `"Development Tools"` |
| Shell 配置 | `~/.bashrc` | `~/.bashrc`（相同） |
