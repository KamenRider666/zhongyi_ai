"""Qdrant 向量数据库 - 中医知识库 RAG（轻量版，替代 Milvus）"""

from typing import List, Optional

from qdrant_client import QdrantClient, models

from src.config import settings


class QdrantStore:
    """Qdrant 向量存储封装

    用法示例:
        store = QdrantStore()
        store.connect()
        store.create_collection()
        store.insert(texts, embeddings, sources, categories)
        results = store.search(query_embedding, top_k=5)
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        collection_name: str | None = None,
        dim: int = 768,
    ):
        self.host = host or settings.QDRANT_HOST
        self.port = port or settings.QDRANT_PORT
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        self.dim = dim
        self.client: QdrantClient | None = None

    def connect(self) -> None:
        """连接 Qdrant"""
        self.client = QdrantClient(host=self.host, port=self.port)

    def disconnect(self) -> None:
        """断开连接"""
        if self.client:
            self.client.close()
            self.client = None

    def collection_exists(self) -> bool:
        """检查集合是否存在"""
        if self.client is None:
            self.connect()
        return self.client.collection_exists(self.collection_name)

    def create_collection(self) -> None:
        """创建知识库集合"""
        if self.client is None:
            self.connect()

        if self.client.collection_exists(self.collection_name):
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.dim,
                distance=models.Distance.COSINE,
            ),
        )

    def insert(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        sources: List[str],
        categories: List[str],
        id_start: int = 0,
    ) -> None:
        """插入向量数据

        Args:
            texts: 文本列表
            embeddings: 向量列表
            sources: 来源列表
            categories: 分类列表
            id_start: 起始 ID（多次调用时避免覆盖）
        """
        if self.client is None:
            self.connect()
        if not self.client.collection_exists(self.collection_name):
            self.create_collection()

        points = [
            models.PointStruct(
                id=id_start + i,
                vector=emb,
                payload={
                    "content": text,
                    "source": src,
                    "category": cat,
                },
            )
            for i, (text, emb, src, cat) in enumerate(
                zip(texts, embeddings, sources, categories)
            )
        ]

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> List[dict]:
        """向量检索

        Args:
            query_embedding: 查询向量
            top_k: 返回结果数
            category: 按分类过滤（如 fangji/herb/acupoint/classic）

        Returns:
            相关知识片段列表
        """
        if self.client is None:
            self.connect()

        query_filter = None
        if category:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="category",
                        match=models.MatchValue(value=category),
                    )
                ]
            )

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        hits = []
        for hit in results:
            hits.append(
                {
                    "content": hit.payload.get("content"),
                    "source": hit.payload.get("source"),
                    "category": hit.payload.get("category"),
                    "score": hit.score,
                }
            )
        return hits

    def delete_collection(self) -> None:
        """删除集合"""
        if self.client is None:
            self.connect()
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)

    def get_stats(self) -> dict:
        """获取集合统计信息"""
        if self.client is None:
            self.connect()
        if not self.client.collection_exists(self.collection_name):
            return {"exists": False, "points": 0}
        info = self.client.get_collection(self.collection_name)
        return {
            "exists": True,
            "points": info.points_count if info else 0,
            "indexed_vectors": info.indexed_vectors_count if info else 0,
        }
