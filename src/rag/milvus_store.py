"""Milvus 向量数据库 - 中医知识库 RAG"""

from typing import List, Optional

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
    connections,
    utility,
)


class MilvusStore:
    """Milvus 向量存储封装"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = "tcm_knowledge",
        dim: int = 768,
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.dim = dim
        self.collection: Optional[Collection] = None

    def connect(self) -> None:
        """连接 Milvus"""
        connections.connect(host=self.host, port=self.port)

    def disconnect(self) -> None:
        """断开连接"""
        connections.disconnect("default")

    def create_collection(self) -> None:
        """创建知识库集合"""
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            return

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
        ]
        schema = CollectionSchema(fields, description="中医知识库")

        self.collection = Collection(self.collection_name, schema)

        # 创建 IVF_FLAT 索引
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        self.collection.create_index("embedding", index_params)

    def insert(self, texts: List[str], embeddings: List[List[float]], sources: List[str], categories: List[str]) -> None:
        """插入向量数据"""
        if self.collection is None:
            self.create_collection()

        entities = [
            texts,
            sources,
            categories,
            embeddings,
        ]
        self.collection.insert(entities)
        self.collection.flush()

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> List[dict]:
        """向量检索"""
        if self.collection is None:
            self.collection = Collection(self.collection_name)

        self.collection.load()

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        expr = f'category == "{category}"' if category else None

        results = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["content", "source", "category"],
        )

        hits = []
        for hit in results[0]:
            hits.append(
                {
                    "content": hit.entity.get("content"),
                    "source": hit.entity.get("source"),
                    "category": hit.entity.get("category"),
                    "score": hit.score,
                }
            )
        return hits

    def delete_collection(self) -> None:
        """删除集合"""
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
