"""RAG 语义检索工具 - 混合检索（稠密向量 + BM25 稀疏）"""

import logging
from typing import Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.rag.bm25_store import BM25Store
from src.rag.embedding import DashScopeEmbedding
from src.rag.qdrant_store import QdrantStore
from src.rag.retriever import TCMRetriever
from src.config import settings

logger = logging.getLogger(__name__)

# 模块级单例：BM25 索引全局共享（避免每次创建工具实例都重建索引）
_bm25_store: Optional[BM25Store] = None


# === 工具输入模型 ===

class RAGSearchInput(BaseModel):
    query: str = Field(description="自然语言查询，如「活血化瘀」「风寒感冒怎么治」")
    top_k: int = Field(default=5, description="返回结果数量，默认 5 条")


# === 工厂函数 ===

def get_bm25_store() -> Optional[BM25Store]:
    """获取全局共享的 BM25Store 单例（延迟初始化）

    首次调用时从 Qdrant 加载全量文档构建 BM25 索引。
    构建失败时返回 None，检索器自动退化为纯稠密检索。
    """
    global _bm25_store
    if _bm25_store is not None:
        return _bm25_store

    try:
        store = BM25Store()
        qdrant = QdrantStore()
        qdrant.connect()
        count = store.build_from_qdrant(qdrant)
        if count > 0:
            _bm25_store = store
            logger.info(f"BM25 索引就绪: {count} 篇文档")
            return _bm25_store
        else:
            logger.warning("BM25 索引为空（Qdrant 无文档），混合检索降级为纯稠密")
            return None
    except Exception as e:
        logger.warning(f"BM25 索引构建失败，混合检索降级为纯稠密: {e}")
        return None


def create_tcm_retriever() -> TCMRetriever:
    """创建 TCMRetriever 实例（延迟初始化，每个 worker 一个）

    自动注入 BM25Store 实现混合检索；BM25 不可用时退化为纯稠密。
    """
    embedding = DashScopeEmbedding(
        api_key=settings.DASHSCOPE_API_KEY,
        dimension=1024,
    )
    store = QdrantStore()
    store.connect()
    bm25 = get_bm25_store()
    return TCMRetriever(vector_store=store, embedding_service=embedding, bm25_store=bm25)


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
        "混合检索中医知识库（稠密向量 + BM25 关键词 + RRF 融合排序）。"
        "从药典、方剂、经典文献中查找与用户问题相关的内容。"
        "适用于模糊查询、概念关联、文献引用、精确术语匹配等场景。"
        "与 search_fangji/search_herb 不同，本工具同时基于语义相似度和关键词精确匹配。"
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
