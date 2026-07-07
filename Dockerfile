# 中医 AI Agent Dockerfile
# 基于 uv + Python 3.13 slim

FROM python:3.13-slim

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 设置工作目录
WORKDIR /app

# 优化 Docker 构建
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

# 先复制依赖文件（利用 Docker 缓存层）
COPY pyproject.toml ./

# 安装依赖（不安装项目本身）
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 复制源码
COPY . .

# 安装项目本身
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# 创建非 root 用户
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uv", "run", "python", "-m", "src.api.server"]
