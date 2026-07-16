"""P3 集成测试：Agent 行为与 System Prompt 质量"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.agent.core import (
    TCM_SYSTEM_PROMPT,
    create_tcm_agent,
    run_agent_stream,
)
from src.tools.tcm_tools import FangjiSearchTool


class TestSystemPrompt:
    """System Prompt 质量检查"""

    def test_contains_core_principles(self):
        assert "辨证" in TCM_SYSTEM_PROMPT
        assert "方剂" in TCM_SYSTEM_PROMPT
        assert "体质" in TCM_SYSTEM_PROMPT
        assert "黄帝内经" in TCM_SYSTEM_PROMPT or "伤寒论" in TCM_SYSTEM_PROMPT

    def test_contains_warning_keywords(self):
        assert "医师指导" in TCM_SYSTEM_PROMPT
        assert "立即就医" in TCM_SYSTEM_PROMPT
        assert "有毒" in TCM_SYSTEM_PROMPT or "毒性" in TCM_SYSTEM_PROMPT

    def test_contains_disclaimer(self):
        assert ("免责" in TCM_SYSTEM_PROMPT) or ("建议仅供参考" in TCM_SYSTEM_PROMPT)
        assert "不能替代" in TCM_SYSTEM_PROMPT

    def test_contains_tool_strategy(self):
        assert "工具选择策略" in TCM_SYSTEM_PROMPT or "精确查询" in TCM_SYSTEM_PROMPT
        assert "语义查询" in TCM_SYSTEM_PROMPT or "知识图谱" in TCM_SYSTEM_PROMPT

    def test_contains_multiround_guidance(self):
        assert "多轮对话" in TCM_SYSTEM_PROMPT or "对话是连续的" in TCM_SYSTEM_PROMPT

    def test_contains_answer_structure(self):
        assert "辨证分析" in TCM_SYSTEM_PROMPT or "治则治法" in TCM_SYSTEM_PROMPT
        assert "调护建议" in TCM_SYSTEM_PROMPT or "方药推荐" in TCM_SYSTEM_PROMPT


class TestAgentCreation:
    """Agent 创建测试 — 使用真实工具实例而非 Mock"""

    def test_create_agent_returns_compiled_graph(self):
        """创建 Agent 返回 CompiledStateGraph"""
        from src.agent.llm import QwenChatModel

        llm = QwenChatModel()
        tools = [FangjiSearchTool()]

        agent = create_tcm_agent(llm=llm, tools=tools)

        assert agent is not None
        assert hasattr(agent, "astream_events")

    def test_create_agent_with_checkpointer(self):
        """创建带 checkpointer 的 Agent"""
        from langgraph.checkpoint.memory import InMemorySaver
        from src.agent.llm import QwenChatModel

        llm = QwenChatModel()
        tools = [FangjiSearchTool()]
        checkpointer = InMemorySaver()

        agent = create_tcm_agent(llm=llm, tools=tools, checkpointer=checkpointer)

        assert agent is not None


class TestAgentStream:
    """Agent 流式输出测试"""

    @pytest.mark.asyncio
    async def test_run_agent_stream_yields_events(self):
        """流式输出正确产出 token 事件"""
        mock_agent = AsyncMock()

        async def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_chat_model_stream",
                "name": "QwenChatModel",
                "data": {"chunk": MagicMock(content="您好")},
                "metadata": {},
                "tags": [],
                "run_id": "test-run",
            }
            yield {
                "event": "on_chat_model_stream",
                "name": "QwenChatModel",
                "data": {"chunk": MagicMock(content="，这是测试回答。")},
                "metadata": {},
                "tags": [],
                "run_id": "test-run",
            }

        mock_agent.astream_events = mock_stream_events

        events = []
        async for event in run_agent_stream(mock_agent, "测试", "test-thread"):
            events.append(event)

        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) == 2
        assert token_events[0]["content"] == "您好"

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1

    @pytest.mark.asyncio
    async def test_run_agent_stream_tool_events(self):
        """工具调用事件正确产出"""
        mock_agent = AsyncMock()

        async def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_tool_start",
                "name": "search_fangji",
                "data": {"input": {"keyword": "麻黄汤"}},
                "metadata": {},
                "tags": [],
                "run_id": "test-run",
            }
            yield {
                "event": "on_tool_end",
                "name": "search_fangji",
                "data": {},
                "metadata": {},
                "tags": [],
                "run_id": "test-run",
            }

        mock_agent.astream_events = mock_stream_events

        events = []
        async for event in run_agent_stream(mock_agent, "麻黄汤是什么", "test-thread"):
            events.append(event)

        tool_starts = [e for e in events if e["type"] == "tool_start"]
        tool_ends = [e for e in events if e["type"] == "tool_end"]

        assert len(tool_starts) == 1
        assert tool_starts[0]["tool_name"] == "search_fangji"
        assert len(tool_ends) == 1

    @pytest.mark.asyncio
    async def test_run_agent_stream_error_handling(self):
        """流式输出异常时产出 error 事件"""
        mock_agent = AsyncMock()

        # 同步抛出异常，在 try/except 中被捕获
        def raise_error(*args, **kwargs):
            raise RuntimeError("API 调用失败")

        mock_agent.astream_events = raise_error

        events = []
        async for event in run_agent_stream(mock_agent, "测试", "test-thread"):
            events.append(event)

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "API 调用失败" in error_events[0]["message"]
