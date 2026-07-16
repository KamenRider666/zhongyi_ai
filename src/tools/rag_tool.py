"""RAG 语义检索工具 - 向量知识库查询"""

from typing import Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.rag.embedding import DashScopeEmbedding
from src.rag.qdrant_store import QdrantStore
from src.rag.retriever import TCMRetriever
from src.config import settings


# === 工具输入模型 ===

class RAGSearchInput(BaseModel):
    query: str = Field(description="自然语言查询，如「活血化瘀」「风寒感冒怎么治」")
    top_k: int = Field(default=5, description="返回结果数量，默认 5 条")


# === 工厂函数 ===

def create_tcm_retriever() -> TCMRetriever:
    """创建 TCMRetriever 实例（延迟初始化，每个 worker 一个）"""
    embedding = DashScopeEmbedding(
        api_key=settings.DASHSCOPE_API_KEY,
        dimension=1024,
    )
    store = QdrantStore()
    store.connect()
    return TCMRetriever(vector_store=store, embedding_service=embedding)


# === RAG 检索工具 ===

class TCMKnowledgeSearchTool(BaseTool):
    """语义检索中医知识库

    通过向量相似度搜索，从中医经典文献、药典、方剂等知识库中找到与用户问题
    语义相关的段落。适用于：
    - 模糊查询（用户描述症状而非精确术语）
    - 跨领域关联（如「活血」和「化瘀」语义相近但字面不同）
    - 检索经典文献中的相关论述
    """

    name: str = "search_tcm_knowledge"
    description: str = (
        "语义检索中医知识库。将自然语言查询转为向量，在药典、方剂、经典文献中"
        "查找语义相近的内容。适用于模糊查询、概念关联、文献引用等场景。"
        "与 search_fangji/search_herb 不同，本工具基于语义相似度而非关键词匹配。"
    )
    args_schema: Type[BaseModel] = RAGSearchInput

    retriever: TCMRetriever = Field(
        default_factory=create_tcm_retriever,
        exclude=True,
    )

    def _run(self, query: str, top_k: int = 5) -> str:
        """执行语义检索

        Args:
            query: 自然语言查询文本
            top_k: 返回结果数

        Returns:
            格式化后的检索结果
        """
        try:
            results = self.retriever.retrieve(query=query, top_k=top_k)
            if not results:
                return f"未找到与「{query}」语义相关的中医知识。"
            return self.retriever.format_context(results)
        except Exception as e:
            return f"知识库检索失败：{str(e)}。请尝试使用 search_fangji 或 search_herb 进行精确查询。"
