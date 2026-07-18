"""RAG 检索器 - 混合检索（稠密向量 + BM25 稀疏 + RRF 融合）"""

import logging
from typing import List, Optional

from src.rag.bm25_store import BM25Store
from src.rag.embedding import EmbeddingService
from src.rag.fusion import rrf_fusion
from src.rag.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)


class TCMRetriever:
    """中医知识检索器 — 混合检索

    检索策略:
      1. 稠密检索 (Qdrant 向量): 语义相似度匹配，擅长模糊查询和概念关联
      2. 稀疏检索 (BM25):       关键词精确匹配，擅长方名/药名/穴位名命中
      3. RRF 融合:               两路结果按倒数排名融合，兼顾语义和精确匹配

    当 bm25_store 为 None 时自动退化为纯稠密检索（向后兼容）。
    """

    def __init__(
        self,
        vector_store: QdrantStore,
        embedding_service: EmbeddingService,
        bm25_store: Optional[BM25Store] = None,
    ):
        self.store = vector_store
        self.embedding = embedding_service
        self.bm25 = bm25_store

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> List[dict]:
        """混合检索相关知识

        Args:
            query: 查询文本
            top_k: 最终返回结果数
            category: 按分类过滤（herb/formula/disease/syndrome/symptom/therapy）

        Returns:
            融合排序后的相关知识片段列表
        """
        # 召回量扩大到 top_k 的 4 倍，给 RRF 融合留足候选
        recall_k = top_k * 4

        # ① 稠密检索
        query_embedding = self.embedding.encode_query(query)
        dense_results = self.store.search(
            query_embedding=query_embedding,
            top_k=recall_k,
            category=category,
        )

        # ② 稀疏检索 + RRF 融合（BM25 可用时）
        if self.bm25 and self.bm25.is_ready:
            sparse_results = self.bm25.search(query, top_k=recall_k, category=category)

            if sparse_results:
                fused = rrf_fusion(
                    dense_results=dense_results,
                    sparse_results=sparse_results,
                    top_k=top_k,
                )
                logger.debug(
                    f"混合检索: dense={len(dense_results)}, "
                    f"sparse={len(sparse_results)}, fused={len(fused)}"
                )
                return fused
            # BM25 无结果时退化到纯稠密
            logger.debug("BM25 无结果，退化为纯稠密检索")

        # 纯稠密检索（BM25 不可用或无结果）
        return dense_results[:top_k]

    def format_context(self, results: List[dict]) -> str:
        """将检索结果格式化为上下文文本"""
        if not results:
            return ""

        lines = ["## 相关知识库检索结果：\n"]
        for i, hit in enumerate(results, 1):
            source_info = f"（出处：{hit['source']}）" if hit.get("source") else ""
            lines.append(f"{i}. {hit['content']}{source_info}\n")

        return "\n".join(lines)
