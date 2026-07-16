"""FastAPI 服务 - 中医 AI Agent API"""

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agent.core import TCM_SYSTEM_PROMPT, create_tcm_agent
from src.agent.llm import create_qwen_llm
from src.config import settings
from src.tools.tcm_tools import get_all_tools


# === 请求/响应模型 ===

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None
    stream: bool = False


class ChatResponse(BaseModel):
    reply: str
    system_prompt: str = TCM_SYSTEM_PROMPT


class FangjiResponse(BaseModel):
    name: str
    source: str
    category: str
    composition: str
    efficacy: str
    indications: str


# === 全局 Agent ===

agent_executor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    global agent_executor
    print("🚀 中医 AI Agent 启动中...")

    llm = create_qwen_llm(
        api_key=settings.DASHSCOPE_API_KEY,
        model=settings.QWEN_MODEL,
    )
    tools = get_all_tools()
    agent_executor = create_tcm_agent(llm=llm, tools=tools)

    print(f"✓ 模型: {settings.QWEN_MODEL}")
    print(f"✓ 工具: {[t.name for t in tools]}")
    print(f"✓ 服务已就绪: http://{settings.HOST}:{settings.PORT}")

    yield

    print("👋 中医 AI Agent 已关闭")


# === FastAPI 应用 ===

app = FastAPI(
    title="中医 AI Agent",
    description="基于 LangChain + 通义千问 + Milvus + SQLite 的中医智能助手",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """健康检查"""
    return {"status": "ok", "service": "中医 AI Agent", "version": "0.1.0"}


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "model": settings.QWEN_MODEL,
        "tools_available": True,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """对话接口"""
    if agent_executor is None:
        raise HTTPException(status_code=503, detail="Agent 未初始化")

    try:
        result = await agent_executor.ainvoke({"messages": [{"role": "user", "content": request.message}]})
        messages = result.get("messages", [])
        reply = messages[-1].content if messages else "抱歉，我暂时无法回答这个问题。"
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 执行错误: {str(e)}")


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口"""
    if agent_executor is None:
        raise HTTPException(status_code=503, detail="Agent 未初始化")

    async def generate():
        try:
            result = await agent_executor.ainvoke({"messages": [{"role": "user", "content": request.message}]})
            messages = result.get("messages", [])
            reply = messages[-1].content if messages else "抱歉，我暂时无法回答这个问题。"
            yield f"data: {reply}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: 错误: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
