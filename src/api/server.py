"""FastAPI 服务 - 中医 AI Agent API（含用户认证 + 前端页面）"""

import io
import json
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

from src.agent.core import TCM_SYSTEM_PROMPT, create_tcm_agent, run_agent_stream
from src.agent.llm import create_qwen_llm
from src.api.auth import get_current_user, router as auth_router
from src.config import settings
from src.tools.tcm_tools import get_all_tools


# === 请求/响应模型 ===
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    system_prompt: str = TCM_SYSTEM_PROMPT


# === 全局 Agent ===
agent_executor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_executor
    print("🚀 中医 AI Agent 启动中...")

    llm = create_qwen_llm(
        api_key=settings.DASHSCOPE_API_KEY,
        model=settings.QWEN_MODEL,
    )
    tools = get_all_tools()
    checkpointer = InMemorySaver()
    agent_executor = create_tcm_agent(llm=llm, tools=tools, checkpointer=checkpointer)

    print(f"✓ 模型: {settings.QWEN_MODEL}")
    print(f"✓ 工具: {[t.name for t in tools]}")
    print(f"✓ 多轮对话记忆: 已启用 (InMemorySaver)")
    print(f"✓ 服务已就绪: http://{settings.HOST}:{settings.PORT}")

    yield
    print("👋 中医 AI Agent 已关闭")


# === FastAPI 应用 ===
app = FastAPI(
    title="中医 AI Agent",
    description="基于 LangChain + 通义千问 + MySQL + Qdrant 的中医智能助手",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册认证路由
app.include_router(auth_router)

# 挂载前端静态文件夹
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# === 前端页面 ===
@app.get("/app")
async def app_page():
    """主应用页面（登录/注册/对话一体）"""
    return FileResponse(str(static_dir / "index.html"))


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "中医 AI Agent",
        "version": "0.2.0",
        "docs": "/docs",
        "app": "/app",
    }


@app.get("/health")
async def health():
    """健康检查 — 检测后端服务连通性"""
    checks = {}
    all_ok = True

    # MySQL
    try:
        from src.data.database import get_database
        db = get_database()
        checks["mysql"] = "ok" if db.ping() else "fail"
        if checks["mysql"] != "ok":
            all_ok = False
    except Exception as e:
        checks["mysql"] = f"error: {e}"
        all_ok = False

    # Neo4j
    try:
        from src.graphrag.graph_store import Neo4jGraphStore
        from src.config import settings as s
        store = Neo4jGraphStore(uri=s.NEO4J_URI, user=s.NEO4J_USER, password=s.NEO4J_PASSWORD)
        store.connect()
        store.execute_query("RETURN 1")
        store.close()
        checks["neo4j"] = "ok"
    except Exception as e:
        checks["neo4j"] = f"error: {e}"
        all_ok = False

    # Qdrant
    try:
        from src.rag.qdrant_store import QdrantStore
        from src.config import settings as s
        qs = QdrantStore(dim=1024)
        qs.connect()
        ok = qs.collection_exists()
        qs.disconnect()
        checks["qdrant"] = "ok" if ok else "no_collection"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"
        all_ok = False

    return {
        "status": "healthy" if all_ok else "degraded",
        "model": settings.QWEN_MODEL,
        "tools_available": agent_executor is not None,
        "checks": checks,
    }


# === 对话接口（需要登录） ===
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, username: str = Depends(get_current_user)):
    """对话接口（需要 JWT 认证）"""
    if agent_executor is None:
        raise HTTPException(status_code=503, detail="Agent 未初始化")

    session_id = request.session_id or f"{username}-{uuid.uuid4().hex[:8]}"

    try:
        result = await agent_executor.ainvoke(
            {"messages": [{"role": "user", "content": request.message}]},
            config={"configurable": {"thread_id": session_id}},
        )
        messages = result.get("messages", [])
        reply = messages[-1].content if messages else "抱歉，我暂时无法回答这个问题。"
        return ChatResponse(reply=reply, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 执行错误: {str(e)}")


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, username: str = Depends(get_current_user)):
    """流式对话接口（需要 JWT 认证）"""
    if agent_executor is None:
        raise HTTPException(status_code=503, detail="Agent 未初始化")

    session_id = request.session_id or f"{username}-{uuid.uuid4().hex[:8]}"

    async def generate():
        try:
            async for event in run_agent_stream(agent_executor, request.message, session_id):
                yield f"event: {event['type']}\n"
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\n"
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "X-Session-Id": session_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.server:app", host=settings.HOST, port=settings.PORT, reload=True)
