@echo off
REM 中医 AI Agent 一键启动脚本 (Windows)

echo =========================================
echo   中医 AI Agent 启动脚本
echo =========================================

echo.
echo 🔍 检查运行环境...
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ uv 未安装
    exit /b 1
)
echo ✓ uv 已就绪

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python 未安装
    exit /b 1
)
echo ✓ Python 已就绪

echo.
echo 📦 初始化中医数据...
uv run python -m src.data.seed

echo.
echo 🕸️ 初始化知识图谱（可选，需 Neo4j 运行）...
uv run python -m src.graphrag.seed_graph 2>nul
if %errorlevel% neq 0 (
    echo ⚠️ Neo4j 未连接，知识图谱功能暂不可用
    echo    请先启动 Neo4j: docker-compose up -d neo4j
)

echo.
echo 🚀 启动中医 AI Agent 服务...
echo    API 地址: http://localhost:8000
echo    API 文档: http://localhost:8000/docs
echo.
uv run python -m src.api.server
