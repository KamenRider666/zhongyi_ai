"""Agent 核心逻辑 - 中医 AI 助手"""

from typing import Any, Dict, List

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool

from src.agent.llm import QwenChatModel


TCM_SYSTEM_PROMPT = """你是一位资深的中医 AI 助手，精通中医经典理论和临床实践。

## 你的核心能力：
1. **辨证论治**：根据用户描述的症状，运用八纲辨证、脏腑辨证等方法进行分析
2. **方剂推荐**：推荐合适的经典方剂，说明组成、用法、功效、禁忌
3. **体质辨识**：通过问答判断用户体质类型（平和质、气虚质、阳虚质、阴虚质、痰湿质、湿热质、血瘀质、气郁质、特禀质）
4. **药材知识**：解答中药材的性味归经、功效主治、用法用量
5. **穴位推荐**：根据症状推荐合适的经络穴位进行按摩或艾灸
6. **养生建议**：结合季节、体质提供食疗和养生方案

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
    verbose: bool = False,
) -> AgentExecutor:
    """创建中医 AI Agent

    Args:
        llm: 通义千问 LLM 实例
        tools: 可用工具列表（方剂查询、药材查询等）
        verbose: 是否输出详细日志

    Returns:
        AgentExecutor 实例
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", TCM_SYSTEM_PROMPT),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_openai_tools_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=verbose,
        handle_parsing_errors=True,
        max_iterations=5,
    )

    return agent_executor


async def run_agent(
    agent_executor: AgentExecutor,
    user_input: str,
    chat_history: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """运行 Agent 处理用户输入

    Args:
        agent_executor: Agent 执行器
        user_input: 用户输入文本
        chat_history: 对话历史

    Returns:
        Agent 执行结果
    """
    result = await agent_executor.ainvoke({"input": user_input})
    return result
