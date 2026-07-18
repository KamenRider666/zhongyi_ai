"""Agent 核心逻辑 - 中医 AI 助手"""

import logging
import time
from typing import Any, AsyncIterator, Dict, List

from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from src.agent.llm import QwenChatModel

# 追踪专用 logger，输出到控制台和文件
tracer = logging.getLogger("tcm.trace")
tracer.setLevel(logging.DEBUG)

# 终端 handler：简洁格式
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    "[%(asctime)s] %(message)s", datefmt="%H:%M:%S"
))
tracer.addHandler(console_handler)

# 文件 handler：完整 JSON 日志（便于事后分析）
try:
    from pathlib import Path
    _log_dir = Path(__file__).parent.parent.parent / "logs"
    _log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(
        str(_log_dir / "trace.log"), encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    tracer.addHandler(file_handler)
except Exception:
    pass  # 文件日志不可用时忽略


# === LLM 回调：追踪每次模型调用 ===

class TracingCallback(BaseCallbackHandler):
    """LangChain 回调，记录 LLM 调用的 token 消耗和耗时"""

    def __init__(self):
        self.llm_calls: List[Dict] = []  # 累计本次会话的 LLM 调用记录
        self._current_start: float = 0

    def on_llm_start(self, serialized, prompts, **kwargs):
        self._current_start = time.time()
        tracer.debug(f"🤖 LLM 调用 #{len(self.llm_calls)+1}: model={serialized.get('name','?')}")

    def on_llm_end(self, response, **kwargs):
        elapsed = time.time() - self._current_start
        usage = {}
        if hasattr(response, "llm_output") and response.llm_output:
            usage = response.llm_output.get("token_usage", {})
        self.llm_calls.append({
            "call": len(self.llm_calls) + 1,
            "duration_ms": round(elapsed * 1000),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        })
        tracer.info(
            f"🤖 LLM #{len(self.llm_calls)} 完成 "
            f"({elapsed*1000:.0f}ms, "
            f"in={usage.get('input_tokens','?')}, "
            f"out={usage.get('output_tokens','?')})"
        )


TCM_SYSTEM_PROMPT = """你是一位资深的中医 AI 助手，精通中医经典理论和临床实践。

## 你的核心能力：
1. **辨证论治**：根据用户描述的症状，运用八纲辨证、脏腑辨证等方法进行分析
2. **方剂推荐**：推荐合适的经典方剂，说明组成、用法、功效、禁忌
3. **体质辨识**：通过问答判断用户体质类型（平和质、气虚质、阳虚质、阴虚质、痰湿质、湿热质、血瘀质、气郁质、特禀质）
4. **药材知识**：解答中药材的性味归经、功效主治、用法用量
5. **穴位推荐**：根据症状推荐合适的经络穴位进行按摩或艾灸
6. **养生建议**：结合季节、体质提供食疗和养生方案
7. **知识图谱推理**：通过知识图谱发现症状→方剂→药材的多跳关联路径，进行深层辨证推理
8. **语义知识检索**：通过向量语义搜索从药典、经典文献中查找相关内容

## 回复规范：
- **简洁**：每次回复控制在 300 字以内，不要写长篇大论
- **不暴露工具**：不要把工具调用的原始结果、工具名称、tool_call_id 展示给用户，要把检索结果自然融入回答
- **通俗**：用日常语言，避免堆砌"诸阳之会""元神之府"等古文术语
- **先答后问**：先回应用户的问题，再追问细节，每次最多问 1-2 个问题

## 工具选择策略：

### 精确查询（关键词匹配）：
- 已知方剂名/药材名 → search_fangji / search_herb
- 已知穴位名或经络 → search_acupoint
- 体质相关问题 → search_constitution

### 语义查询（概念理解）：
- 用户描述症状但未提具体方剂 → search_tcm_knowledge（如「总是手脚冰凉」「睡眠不好」）
- 需要查找经典文献中的论述 → search_tcm_knowledge
- 跨概念关联（「活血」和「化瘀」语义相近）→ search_tcm_knowledge
- 不确定该查哪个精确字段时 → 先用 search_tcm_knowledge，再根据结果用精确工具深挖

### 知识图谱（关系推理）：
- 多个症状综合分析 → search_symptom_path 查找治疗路径
- 查询实体间关联（方剂→药材、药材→归经）→ search_graph_relation
- 搜索特定类型中医实体 → search_graph_entity
- 多跳关系推理，如"头痛→风寒→麻黄汤→桂枝→肺经"

## 多轮对话：
- 对话是连续的，你可以看到之前所有的对话内容
- 请根据上下文记住用户之前提到的症状、体质等信息
- 如果用户的问题与之前的对话相关，请结合历史信息进行分析

## 重要原则：
- 所有分析和建议必须基于中医经典理论（《黄帝内经》《伤寒论》《金匮要略》等）
- 推荐方剂时必须注明出处和组成
- 涉及具体剂量时必须强调"请在医师指导下使用"
- 急重症（胸痛、高热不退、昏迷、大出血等）必须首先建议立即就医
- 有毒药材（附子、乌头、细辛等）必须标注毒性并警告
- 回答结构清晰：辨证分析 → 治则治法 → 方药推荐 → 调护建议

## 免责声明：
本助手提供的中医建议仅供参考，不能替代专业医师的诊断和治疗。如有身体不适，请及时就医。"""


def create_tcm_agent(
    llm: QwenChatModel,
    tools: List[BaseTool],
    checkpointer: InMemorySaver | None = None,
    debug: bool = False,
) -> CompiledStateGraph:
    """创建中医 AI Agent

    Args:
        llm: 通义千问 LLM 实例
        tools: 可用工具列表（方剂查询、药材查询等）
        checkpointer: LangGraph 检查点存储器，用于多轮对话记忆
        debug: 是否开启调试模式

    Returns:
        CompiledStateGraph 实例
    """
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=TCM_SYSTEM_PROMPT,
        checkpointer=checkpointer,
        debug=debug,
    )
    return agent


async def run_agent(
    agent: CompiledStateGraph,
    user_input: str,
    thread_id: str,
    chat_history: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """运行 Agent 处理用户输入（支持多轮对话记忆）

    Args:
        agent: CompiledStateGraph 实例
        user_input: 用户输入文本
        thread_id: 会话 ID，同一 ID 的多次调用共享对话历史
        chat_history: 对话历史（已弃用，由 checkpointer 自动管理）

    Returns:
        Agent 执行结果，包含 "messages" 键
    """
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
    )
    return result


async def run_agent_stream(
    agent: CompiledStateGraph,
    user_input: str,
    thread_id: str,
) -> AsyncIterator[Dict[str, Any]]:
    """流式运行 Agent，逐 token 产出事件（含追踪信息）

    通过 LangGraph astream_events 实现真正的 token 级流式输出，
    同时支持多轮对话记忆（同一 thread_id 共享历史）。

    Yields:
        dict 事件，格式：
        - {"type": "token", "content": "..."}   token 级文本
        - {"type": "tool_start", "tool_name": "...", "tool_input": {...}}  工具开始调用
        - {"type": "tool_end", "tool_name": "...", "tool_output": "...", "duration_ms": 123}  工具调用完成
        - {"type": "done", "trace": {...}}  全部完成，附带追踪摘要
        - {"type": "error", "message": "..."}  出错

    Example:
        async for event in run_agent_stream(agent, "我头痛", "session-1"):
            if event["type"] == "token":
                print(event["content"], end="", flush=True)
    """
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    session_start = time.time()
    tool_count = 0
    tools_called: List[Dict] = []
    tool_timers: Dict[str, float] = {}  # tool_name -> start_time

    tracer.info(f"▶ [trace:{thread_id[:8]}] 用户: {user_input[:80]}")

    try:
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=user_input)]},
            config=config,
            version="v2",
        ):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                content = chunk.content
                # 只产出文本内容（空字符串 = tool_calls chunk，跳过）
                if content and isinstance(content, str):
                    yield {"type": "token", "content": content}

            elif kind == "on_tool_start":
                tool_count += 1
                tool_name = event["name"]
                tool_input = event["data"].get("input", {})
                tool_timers[tool_name] = time.time()

                tracer.info(
                    f"🔧 [trace:{thread_id[:8]}] 调用工具 #{tool_count}: {tool_name}"
                )
                tracer.debug(
                    f"   输入: {str(tool_input)[:200]}"
                )

                yield {
                    "type": "tool_start",
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                }

            elif kind == "on_tool_end":
                tool_name = event["name"]
                tool_output = event["data"].get("output", "")
                duration_ms = 0
                if tool_name in tool_timers:
                    duration_ms = round((time.time() - tool_timers[tool_name]) * 1000)
                    del tool_timers[tool_name]

                tools_called.append({
                    "name": tool_name,
                    "duration_ms": duration_ms,
                    "output_preview": str(tool_output)[:200],
                })

                tracer.info(
                    f"🔧 [trace:{thread_id[:8]}] {tool_name} 完成 "
                    f"({duration_ms}ms, 输出 {len(str(tool_output))} 字符)"
                )

                yield {
                    "type": "tool_end",
                    "tool_name": tool_name,
                    "tool_output": str(tool_output)[:500],
                    "duration_ms": duration_ms,
                }

        total_ms = round((time.time() - session_start) * 1000)

        trace_summary = {
            "thread_id": thread_id,
            "total_ms": total_ms,
            "tool_count": tool_count,
            "tools": tools_called,
        }

        tracer.info(
            f"✓ [trace:{thread_id[:8]}] 完成 "
            f"({total_ms}ms, {tool_count} 次工具调用)"
        )

        yield {"type": "done", "trace": trace_summary}

    except Exception as e:
        total_ms = round((time.time() - session_start) * 1000)
        tracer.error(f"✗ [trace:{thread_id[:8]}] 异常 ({total_ms}ms): {e}")
        yield {"type": "error", "message": str(e)}
