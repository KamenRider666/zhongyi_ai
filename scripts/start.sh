#!/usr/bin/env bash
# 中医 AI Agent 一键启动脚本

set -e

echo "========================================="
echo "  中医 AI Agent 启动脚本"
echo "========================================="

# 检查环境
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo "❌ $1 未安装"
        return 1
    fi
    echo "✓ $1 已就绪: $($1 --version 2>&1 | head -1)"
}

echo ""
echo "🔍 检查运行环境..."
check_command uv
check_command python

# 初始化数据
echo ""
echo "📦 初始化中医数据..."
uv run python -m src.data.seed

# 启动服务
echo ""
echo "🚀 启动中医 AI Agent 服务..."
echo "   API 地址: http://localhost:8000"
echo "   API 文档: http://localhost:8000/docs"
echo ""
uv run python -m src.api.server
