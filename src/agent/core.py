"""Agent 核心逻辑 - 中医 AI 助手"""

from typing import Any, Dict, List

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from src.agent.llm import QwenChatModel


TCM_SYSTEM_PROMPT = """你是一位资深的中医 AI 助手，精通中医经典理论和临床实践。

## 你的核心能力：
1. **辨证论治**：根据用户描述的症状，运用八纲辨证、脏腑辨证等方法进行分析
2. **方剂推荐**：推荐合适的经典方剂，说明组成、用法、功效、禁忌
3. **体质辨识**：通过问答判断用户体质类型（平和质、气虚质、阳虚质、阴虚质、痰湿质、湿热质、血瘀质、气郁质、特禀质）
4. **药材知识**：解答中药材的性味归经、功效主治、用法用量
5. **穴位推荐**：根据症状推荐合适的经络穴位进行按摩或艾灸
6. **养生建议**：结合季节、体质提供食疗和养生方案
7. **知识图谱推理**：通过知识图谱发现症状→方剂→药材的多跳关联路径，进行深层辨证推理

## 知识图谱使用策略：
- 当用户描述多个症状或需要综合分析时，优先使用 search_symptom_path 工具查找治疗路径
- 当需要了解实体间的关联关系（如方剂含哪些药材、药材归哪些经）时，使用 search_graph_relation
- 当需要搜索特定类型的中医实体时，使用 search_graph_entity
- 知识图谱可以发现向量检索难以捕捉的多跳关系，如"头痛→风寒→麻黄汤→桂枝→肺经"

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
    debug: bool = False,
) -> CompiledStateGraph:
    """创建中医 AI Agent

    Args:
        llm: 通义千问 LLM 实例
        tools: 可用工具列表（方剂查询、药材查询等）
        debug: 是否开启调试模式

    Returns:
        CompiledStateGraph 实例
    """
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=TCM_SYSTEM_PROMPT,
        debug=debug,
    )
    return agent


async def run_agent(
    agent: CompiledStateGraph,
    user_input: str,
    chat_history: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """运行 Agent 处理用户输入

    Args:
        agent: CompiledStateGraph 实例
        user_input: 用户输入文本
        chat_history: 对话历史

    Returns:
        Agent 执行结果，包含 "messages" 键
    """
    result = await agent.ainvoke({"messages": [HumanMessage(content=user_input)]})
    return result
