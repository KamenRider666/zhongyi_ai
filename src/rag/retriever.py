"""RAG 检索器 - 整合嵌入和向量检索"""

from typing import List, Optional

from src.rag.embedding import EmbeddingService
# from src.rag.milvus_store import MilvusStore
from src.rag.qdrant_store import QdrantStore

class TCMRetriever:
    """中医知识检索器"""

    def __init__(
        self,
        # milvus_store: MilvusStore,
        vector_store: QdrantStore,
        embedding_service: EmbeddingService,

    ):
        # self.store = milvus_store
        self.store = vector_store
        self.embedding = embedding_service

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> List[dict]:
        """检索相关中医知识

        Args:
            query: 查询文本
            top_k: 返回结果数
            category: 按分类过滤（fangji/herb/acupoint/classic）

        Returns:
            相关知识片段列表
        """
        query_embedding = self.embedding.encode_query(query)
        results = self.store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            category=category,
        )
        return results

    def format_context(self, results: List[dict]) -> str:
        """将检索结果格式化为上下文文本"""
        if not results:
            return ""

        lines = ["## 相关知识库检索结果：\n"]
        for i, hit in enumerate(results, 1):
            source_info = f"（出处：{hit['source']}）" if hit.get("source") else ""
            lines.append(f"{i}. {hit['content']}{source_info}\n")

        return "\n".join(lines)
