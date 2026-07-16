"""通义千问 LLM 封装 - 支持 Tool Calling"""

import json
from typing import Any, Iterator, List, Optional

import dashscope
from dashscope import Generation
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import BaseTool
from pydantic import Field


def _langchain_tools_to_dashscope(tools: List[BaseTool]) -> List[dict]:
    """将 LangChain BaseTool 列表转为 DashScope tools 格式"""
    result = []
    for tool in tools:
        schema = tool.args_schema.model_json_schema() if tool.args_schema else {}
        result.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            },
        })
    return result


def _convert_messages(messages: List[BaseMessage]) -> List[dict]:
    """将 LangChain 消息列表转为通义千问 API 格式"""
    result = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            entry: dict = {"role": "assistant", "content": msg.content or ""}
            # 如果有 tool_calls，需要附加到消息中
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"], ensure_ascii=False),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            result.append(entry)
        elif isinstance(msg, ToolMessage):
            result.append({
                "role": "tool",
                "content": msg.content,
                "tool_call_id": msg.tool_call_id,
                "name": msg.name or "",
            })
    return result


def _parse_tool_calls(choice: Any) -> List[dict]:
    """从 DashScope API 响应中解析 tool_calls"""
    raw = getattr(choice.message, "tool_calls", None)
    if not raw:
        return []
    result = []
    for tc in raw:
        func = tc.get("function", {})
        try:
            arguments = json.loads(func.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            arguments = {}
        result.append({
            "id": tc.get("id", ""),
            "name": func.get("name", ""),
            "args": arguments,
        })
    return result


class QwenChatModel(BaseChatModel):
    """通义千问 Chat Model - 兼容 LangChain，支持 Tool Calling"""

    api_key: str = ""
    model_name: str = "qwen-plus"
    temperature: float = 0.7
    max_tokens: int = 2048
    repetition_penalty: float = 1.1
    tools: Optional[List[dict]] = Field(default=None, exclude=True)

    def bind_tools(
        self,
        tools: List[BaseTool],
        **kwargs: Any,
    ) -> "QwenChatModel":
        """绑定工具列表（LangChain Agent 要求）"""
        formatted = _langchain_tools_to_dashscope(tools)
        return self.model_copy(update={"tools": formatted})

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        dashscope.api_key = self.api_key

        msgs = _convert_messages(messages)
        call_kwargs: dict = {
            "model": self.model_name,
            "messages": msgs,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stop": stop,
            "result_format": "message",
            "repetition_penalty": self.repetition_penalty,
        }
        if self.tools:
            call_kwargs["tools"] = self.tools

        response = Generation.call(**call_kwargs)

        if response.status_code != 200:
            raise Exception(f"DashScope API error: {response.message}")

        choice = response.output.choices[0]
        content = choice.message.content or ""
        tool_calls = _parse_tool_calls(choice)

        message = AIMessage(
            content=content,
            tool_calls=tool_calls,
            additional_kwargs={},
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Iterator[ChatGeneration]:
        dashscope.api_key = self.api_key

        msgs = _convert_messages(messages)
        call_kwargs: dict = {
            "model": self.model_name,
            "messages": msgs,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stop": stop,
            "stream": True,
            "result_format": "message",
            "repetition_penalty": self.repetition_penalty,
        }
        if self.tools:
            call_kwargs["tools"] = self.tools

        response = Generation.call(**call_kwargs)

        prev_content = ""
        # 流式模式下 tool_call arguments 渐进到达（不完整 JSON），
        # 只在 arguments 完整可解析时才 emit
        tool_call_buffers: dict = {}  # {index: {"id": ..., "name": ...}}
        emitted_call_ids: set = set()  # 已 emit 的 call id，避免重复

        for chunk in response:
            if chunk.status_code != 200:
                raise Exception(f"DashScope API stream error: {chunk.message}")
            choice = chunk.output.choices[0]
            full_content = choice.message.content or ""
            # DashScope 流式返回的是累积文本，需要计算增量 delta
            delta_content = full_content[len(prev_content):]
            prev_content = full_content

            # 解析 tool_calls — 流式下 arguments 可能不完整
            raw_tool_calls = getattr(choice.message, "tool_calls", None) or []
            parsed_calls: list = []

            for tc in raw_tool_calls:
                idx = tc.get("index", 0)
                func = tc.get("function", {})
                name = func.get("name", "")
                raw_args = func.get("arguments", "")
                tc_id = tc.get("id", "")

                # 维护 buffer
                if idx not in tool_call_buffers:
                    tool_call_buffers[idx] = {"id": tc_id, "name": name}
                if tc_id:
                    tool_call_buffers[idx]["id"] = tc_id
                if name:
                    tool_call_buffers[idx]["name"] = name

                # 尝试解析 JSON — 只有完整时才 emit
                try:
                    args = json.loads(raw_args)
                    call_obj = {
                        "id": tool_call_buffers[idx]["id"],
                        "name": tool_call_buffers[idx]["name"],
                        "args": args,
                    }
                    # 避免同一个完整 call 被重复 emit
                    call_key = tc_id or f"{name}:{json.dumps(args, sort_keys=True)}"
                    if call_key not in emitted_call_ids:
                        parsed_calls.append(call_obj)
                        emitted_call_ids.add(call_key)
                except (json.JSONDecodeError, TypeError):
                    pass  # arguments 不完整，等下一个 chunk

            # 如果没有增量内容也没有新的完整工具调用，跳过
            if not delta_content and not parsed_calls:
                continue

            message = AIMessageChunk(
                content=delta_content,
                tool_calls=parsed_calls,
                additional_kwargs={},
            )
            yield ChatGenerationChunk(message=message)

    @property
    def _llm_type(self) -> str:
        return "qwen-chat"


def create_qwen_llm(
    api_key: str,
    model: str = "qwen-plus",
    temperature: float = 0.7,
) -> QwenChatModel:
    """创建通义千问 LLM 实例"""
    return QwenChatModel(
        api_key=api_key,
        model_name=model,
        temperature=temperature,
    )
