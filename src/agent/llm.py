"""通义千问 LLM 封装"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from typing import Any, Iterator, List, Optional

import dashscope
from dashscope import Generation


def _convert_messages(messages: List[BaseMessage]) -> List[dict]:
    """将 LangChain 消息转换为通义千问格式"""
    result = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})
    return result


class QwenChatModel(BaseChatModel):
    """通义千问 Chat Model - 兼容 LangChain"""

    api_key: str = ""
    model_name: str = "qwen-plus"
    temperature: float = 0.7
    max_tokens: int = 2048

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        dashscope.api_key = self.api_key

        msgs = _convert_messages(messages)
        response = Generation.call(
            model=self.model_name,
            messages=msgs,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stop=stop,
            result_format="message",
        )

        if response.status_code != 200:
            raise Exception(f"通义千问 API 错误: {response.message}")

        content = response.output.choices[0].message.content
        message = AIMessage(content=content)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Iterator[ChatGeneration]:
        dashscope.api_key = self.api_key

        msgs = _convert_messages(messages)
        response = Generation.call(
            model=self.model_name,
            messages=msgs,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stop=stop,
            stream=True,
            result_format="message",
        )

        full_content = ""
        for chunk in response:
            if chunk.status_code != 200:
                raise Exception(f"通义千问 API 流式错误: {chunk.message}")
            content = chunk.output.choices[0].message.content
            full_content += content
            yield ChatGeneration(message=AIMessage(content=content))

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
