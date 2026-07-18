# Linux 环境搭建指南（OpenCloudOS 版）

> 适用系统：OpenCloudOS 8 / OpenCloudOS 9（腾讯云服务器默认镜像之一）  
> 部署方式：Docker Compose  
> 目标：在一台 OpenCloudOS 服务器上搭建 MySQL、Neo4j、Qdrant、LangFuse 四个基础服务，并部署运行中医 AI Agent 项目

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
- [附录：OpenCloudOS 与其他发行版差异](#附录opencloudos-与其他发行版差异)

---

## 0. 前置准备

### 0.1 系统版本确认

OpenCloudOS 没有 `/etc/redhat-release`，需用以下命令：

```bash
# 标准方式（推荐）
cat /etc/os-release
# 输出示例：
# NAME="OpenCloudOS"
# VERSION="9.0"
# ID="opencloudos"
# ...

# OpenCloudOS 专用
cat /etc/opencloudos-release

# 查看内核版本（OpenCloudOS 9 默认 6.x 定制内核）
uname -r
# 示例: 6.6.114-43.oc9.x86_64
```

> **说明**：
> - OpenCloudOS 8 对应 RHEL 8 血统，OpenCloudOS 9 对应 RHEL 9 血统。
> - 包管理器为 `dnf`（OpenCloudOS 8/9 均可用，`yum` 是 `dnf` 的软链接）。
> - 内核为腾讯定制版（较新），对容器和云场景有优化。

### 0.2 卸载冲突软件（如有）

OpenCloudOS 9 默认可能预装 `podman`、`buildah`，与 Docker 冲突，先清理：

```bash
sudo dnf remove -y docker \
                   docker-client \
                   docker-client-latest \
                   docker-common \
                   docker-latest \
                   docker-latest-logrotate \
                   docker-logrotate \
                   docker-engine \
                   podman \
                   runc \
                   buildah 2>/dev/null

# 清理残留
sudo dnf autoremove -y
```

### 0.3 安装 Docker

OpenCloudOS 9 兼容 CentOS Stream 9 的 Docker 源，直接使用：

```bash
# 安装 dnf 插件（提供 config-manager）
sudo dnf install -y dnf-plugins-core

# 添加 Docker 官方源（CentOS 9 源，OpenCloudOS 9 兼容）
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# 国内推荐用阿里云镜像加速（二选一）：
# sudo dnf config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo

# 安装 Docker
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

### 0.4 启动并设置开机自启

```bash
sudo systemctl enable --now docker

# 验证
docker --version           # Docker version 24.x.x
docker compose version     # Docker Compose version v2.x.x

# 运行测试镜像
sudo docker run hello-world
```

> **常见问题**：若启动报 `iptables: No chain/target/match by that name`，执行：
> ```bash
> sudo systemctl restart docker
> ```

### 0.5 配置 Docker 镜像加速（国内必做）

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://docker.m.daocloud.io"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  }
}
EOF
sudo systemctl daemon-reload && sudo systemctl restart docker
```

> `mirror.ccs.tencentyun.com` 是腾讯云内网镜像加速，OpenCloudOS 在腾讯云上可免公网流量拉镜像。

### 0.6 创建项目目录

```bash
# 创建 /data/tcm-services 目录（放在 /data 数据盘，不放 /root）
sudo mkdir -p /data/tcm-services
sudo chown -R $(whoami):$(whoami) /data/tcm-services
cd /data/tcm-services
mkdir -p mysql_data neo4j_data qdrant_data langfuse_data
```

> **为什么放 /data**：云服务器上 `/data` 通常是独立数据盘，容量更大、重装系统不丢数据，比放 `/root` 更规范。  
> 若你的服务器没有 `/data` 盘，可改用 `/opt/tcm-services` 或保留 `/data/tcm-services`。

### 0.7 关闭 SELinux（避免 Docker 挂载权限问题）

OpenCloudOS 默认 SELinux 为 enforcing，会导致 Docker 容器无法读写挂载目录。推荐关闭：

```bash
# 查看当前状态
getenforce
# 输出: Enforcing

# 临时关闭（立即生效，重启后失效）
sudo setenforce 0

# 永久关闭（需重启生效）
sudo sed -i 's/^SELINUX=enforcing$/SELINUX=disabled/' /etc/selinux/config

# 验证配置已写入
grep ^SELINUX /etc/selinux/config
# SELINUX=disabled
```

> **替代方案**（不愿关闭 SELinux 时）：在每个 `docker run` 的挂载项后加 `:z`，例如 `-v $(pwd)/mysql_data:/var/lib/mysql:z`，Docker 会自动调整 SELinux 标签。统一 compose 方式下也同理。

### 0.8 安装构建依赖

部分 Python 包（如 `mysqlclient`、`lxml`）需要编译，提前装好工具链：

```bash
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y gcc gcc-c++ make \
                    openssl-devel bzip2-devel libffi-devel zlib-devel \
                    wget curl git
```

### 0.9 安装 Python 3.11+

项目要求 Python 3.11 或更高版本。**OpenCloudOS 9 默认 Python 3.9，不满足要求**，需手动安装。

#### 方式一：通过 uv 自动管理（最省心，推荐）

让 `uv` 自行下载管理 Python，无需手动装系统级 Python：

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# uv 自动下载并管理 Python 3.12
uv python install 3.12
uv python list
```

> 项目 `uv sync` 时会自动选用 uv 管理的 Python，无需 `python3 --version` 满足 3.11+。

#### 方式二：系统安装 Python 3.11/3.12（OpenCloudOS 9 AppStream）

```bash
# 查看可用 Python 模块
sudo dnf module list python*

# 安装 Python 3.11
sudo dnf install -y python3.11 python3.11-devel python3.11-pip

# 验证
python3.11 --version   # Python 3.11.x
```

> OpenCloudOS 9 仓库若没有 3.12，可从源码编译：
> ```bash
> cd /tmp
> wget https://www.python.org/ftp/python/3.12.4/Python-3.12.4.tgz
> tar xzf Python-3.12.4.tgz
> cd Python-3.12.4
> ./configure --enable-optimizations --prefix=/usr/local
> make -j$(nproc)
> sudo make altinstall
> python3.12 --version
> ```

### 0.10 安装 Git

```bash
sudo dnf install -y git
git --version
```

### 0.11 安装 uv 包管理器

项目使用 [uv](https://github.com/astral-sh/uv) 管理依赖，比 pip 快 10 倍以上。

```bash
# 如果 0.9 方式一已装，跳过此步
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# 验证
uv --version
```

### 0.12 获取通义千问 API Key

1. 打开 [阿里云百炼平台](https://bailian.console.aliyun.com/)
2. 登录或注册阿里云账号
3. 进入 **模型广场 → API-KEY 管理**
4. 创建一个新的 API Key，复制保存

> 项目同时使用 DashScope API 做 **LLM 对话** 和 **Embedding 向量化**，一个 Key 即可。

### 0.13 配置 .env 文件

在项目根目录创建 `.env` 文件（参考第 8 节的模板）：

```bash
cd /data/tcm-services/zhongyi-ai

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
cd /data/tcm-services
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
cd /data/tcm-services/zhongyi-ai
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
cd /data/tcm-services/zhongyi-ai
uv run python -m src.api.server
```

服务启动后：
- **对话界面**：`http://<服务器IP>:8000`
- **API 文档**：`http://<服务器IP>:8000/docs`

### 11.2 一键启动脚本

项目自带 `scripts/start.sh`，会自动检查环境、初始化数据、启动服务：

```bash
cd /data/tcm-services/zhongyi-ai
bash scripts/start.sh
```

### 11.3 使用 systemd 设为开机自启

创建 systemd 服务文件（自动用当前用户生成，项目目录固定为 `/data/tcm-services`）：

```bash
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
WorkingDirectory=/data/tcm-services/zhongyi-ai
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

# 查看日志
sudo journalctl -u zhongyi-ai -f
```

> **注意**：
> - 项目目录固定为 `/data/tcm-services/zhongyi-ai`，无需手动替换。
> - `uv` 的路径仍用当前用户的家目录（`~/.local/bin` 或 `~/.cargo/bin`），脚本会自动填充。
> - 如果用了系统 Python 3.11 而非 uv 管理，确保 `uv run` 能找到正确版本（uv 会优先用自己管理的 Python）。

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

### 1.2 创建 compose 文件并启动

```bash
cd /data/tcm-services

cat > docker-compose.mysql.yml << 'EOF'
services:
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
EOF

# 启动
docker compose -f docker-compose.mysql.yml up -d

# 查看状态
docker compose -f docker-compose.mysql.yml ps

# 停止（需要时）
# docker compose -f docker-compose.mysql.yml down
```

> **SELinux 提示**：若未关闭 SELinux 且挂载目录报权限错误，把挂载项改为 `- ./mysql_data:/var/lib/mysql:z`。

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

### 2.2 创建 compose 文件并启动

```bash
cd /data/tcm-services

cat > docker-compose.neo4j.yml << 'EOF'
services:
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
EOF

# 启动
docker compose -f docker-compose.neo4j.yml up -d

# 查看状态
docker compose -f docker-compose.neo4j.yml ps

# 查看日志
# docker compose -f docker-compose.neo4j.yml logs -f

# 停止（需要时）
# docker compose -f docker-compose.neo4j.yml down
```

> **SELinux 提示**：若未关闭 SELinux 且挂载目录报权限错误，把挂载项改为 `- ./neo4j_data/data:/data:z`。

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

### 3.2 创建 compose 文件并启动

```bash
cd /data/tcm-services

cat > docker-compose.qdrant.yml << 'EOF'
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant-tcm
    restart: unless-stopped
    ports:
      - "7645:6333"
      - "6334:6334"
    volumes:
      - ./qdrant_data:/qdrant/storage
EOF

# 启动
docker compose -f docker-compose.qdrant.yml up -d

# 查看状态
docker compose -f docker-compose.qdrant.yml ps

# 停止（需要时）
# docker compose -f docker-compose.qdrant.yml down
```

> **SELinux 提示**：若未关闭 SELinux 且挂载目录报权限错误，把挂载项改为 `- ./qdrant_data:/qdrant/storage:z`。

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
cd /data/tcm-services
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

# 查看状态
docker compose -f docker-compose.all.yml ps

# 停止
docker compose -f docker-compose.all.yml down
```

> **SELinux 提示**：若未关闭 SELinux 且卷挂载报权限错误，可在每个 `volumes` 挂载项后加 `:z`，例如 `- ./mysql_data:/var/lib/mysql:z`。

---

## 6. 防火墙配置

OpenCloudOS 默认使用 `firewalld`（不是 Ubuntu 的 `ufw`）。

### 6.1 查看防火墙状态

```bash
sudo systemctl status firewalld
sudo firewall-cmd --state
```

> 若未启用：
> ```bash
> sudo systemctl start firewalld
> sudo systemctl enable firewalld
> ```

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

### 6.3 腾讯云安全组（重要）

OpenCloudOS 常运行在腾讯云上，**除了系统防火墙外，还需在腾讯云控制台配置安全组**：

1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/)
2. 云服务器 → 实例 → 点击你的服务器
3. 安全组 → 配置规则 → 入站规则
4. 添加以下端口放行：

| 端口 | 用途 | 来源 |
|------|------|------|
| 3306 | MySQL | 按需（建议限定 IP） |
| 7474 | Neo4j HTTP | 你的 IP |
| 7644 | Neo4j Bolt | 你的 IP |
| 7645 | Qdrant HTTP | 你的 IP |
| 6334 | Qdrant gRPC | 你的 IP |
| 3000 | LangFuse UI | 你的 IP |
| 8000 | 项目对话界面 | 按需 |

> **安全建议**：MySQL/Neo4j/Qdrant 等数据库端口不要对公网全开（0.0.0.0/0），建议限定为开发机 IP 或内网网段。

### 6.4 若使用 iptables（精简系统）

```bash
sudo iptables -I INPUT -p tcp -m multiport --dports 3306,7474,7644,7645,6334,3000,8000 -j ACCEPT
sudo iptables-save | sudo tee /etc/sysconfig/iptables
```

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
| 项目界面 | `<服务器IP>` | 8000 | — | — |

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

## 附录：OpenCloudOS 与其他发行版差异

### A.1 与 Ubuntu 的区别

| 维度 | Ubuntu | OpenCloudOS |
|------|--------|-------------|
| 包管理 | `apt` / `.deb` | `dnf` / `.rpm` |
| 防火墙 | `ufw` | `firewalld` |
| SELinux | 默认关闭 | 默认 enforcing（建议关闭） |
| 默认 Python | 22.04: 3.10 | 9: 3.9 |
| 系统版本文件 | `/etc/lsb-release` | `/etc/os-release` / `/etc/opencloudos-release` |
| 文件系统 | ext4 | xfs |
| 内核 | 标准 Ubuntu 内核 | 腾讯定制内核（较新） |

### A.2 与 CentOS Stream 9 的区别

| 维度 | CentOS Stream 9 | OpenCloudOS 9 |
|------|----------------|---------------|
| 内核 | 5.14（标准 RHEL 9） | **6.x（腾讯定制，更新）** |
| 发行节奏 | 滚动更新 | 独立版本发布 |
| 云原生优化 | 通用 | 针对腾讯云/容器调优 |
| 商业支持 | Red Hat 订阅 | 腾讯云支持 |
| 生命周期 | Stream 模式较短 | 长期支持（10 年） |
| Docker 源 | CentOS 官方源 | **兼容 CentOS 9 源** |
| 版本标识文件 | `/etc/redhat-release` | `/etc/opencloudos-release`（无 redhat-release） |

### A.3 常用命令对照

```bash
# 安装软件
Ubuntu:       sudo apt install nginx
CentOS:       sudo yum install nginx
OpenCloudOS:  sudo dnf install nginx

# 防火墙开放端口
Ubuntu:       sudo ufw allow 80/tcp
CentOS:       sudo firewall-cmd --permanent --add-port=80/tcp && sudo firewall-cmd --reload
OpenCloudOS:  同 CentOS

# 查看系统版本
Ubuntu:       lsb_release -a
CentOS:       cat /etc/redhat-release
OpenCloudOS:  cat /etc/os-release
```

### A.4 对本项目的影响

项目全部用 Docker 部署，Docker 屏蔽了底层发行版差异。受发行版影响的仅是：

| 环节 | OpenCloudOS 9 对应命令 |
|------|----------------------|
| 安装 Docker | `dnf` + CentOS 9 源 |
| 防火墙开放端口 | `firewall-cmd` |
| 关闭 SELinux | `setenforce 0` + 改 `/etc/selinux/config` |
| Python 3.11+ | `dnf install python3.11` 或 uv 管理 |
| 腾讯云镜像加速 | `mirror.ccs.tencentyun.com`（内网免流量） |

Docker 容器内的 MySQL/Neo4j/Qdrant/LangFuse 与发行版无关，行为完全一致。
