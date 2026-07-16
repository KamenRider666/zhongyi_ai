"""向量嵌入服务 - 支持 DashScope API 和本地 sentence-transformers"""

import os
from typing import List

import dashscope
from dashscope import TextEmbedding


class DashScopeEmbedding:
    """通义千问 Embedding 服务（API 方式，无需本地 GPU）

    使用示例:
        emb = DashScopeEmbedding(dimension=1024)
        vecs = emb.encode(["文本1", "文本2"])
        vec = emb.encode_query("查询文本")
    """

    def __init__(
        self,
        model: str | None = None,
        dimension: int = 1024,
        api_key: str | None = None,
    ):
        self.model = model or TextEmbedding.Models.text_embedding_v3
        self.dimension = dimension
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        if self.api_key:
            dashscope.api_key = self.api_key

    def encode(self, texts: List[str]) -> List[List[float]]:
        """批量将文本转换为向量"""
        # DashScope API 单次最多 10 条
        batch_size = 10
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            resp = TextEmbedding.call(
                model=self.model,
                input=batch,
                dimension=self.dimension,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Embedding API 错误: {resp.code} - {resp.message}")

            for emb in resp.output["embeddings"]:
                all_embeddings.append(emb["embedding"])

        return all_embeddings

    def encode_query(self, query: str) -> List[float]:
        """将单个查询文本转换为向量"""
        return self.encode([query])[0]


# 保持向后兼容的别名（需要本地安装 sentence-transformers）
try:
    from sentence_transformers import SentenceTransformer

    class LocalBGEEmbedding:
        """本地 BGE 模型嵌入（需安装 sentence-transformers + torch）"""

        def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
            self.model = SentenceTransformer(model_name)

        def encode(self, texts: List[str]) -> List[List[float]]:
            embeddings = self.model.encode(texts, normalize_embeddings=True)
            return embeddings.tolist()

        def encode_query(self, query: str) -> List[float]:
            embedding = self.model.encode(query, normalize_embeddings=True)
            return embedding.tolist()

    # 默认使用本地模型
    EmbeddingService = LocalBGEEmbedding

except ImportError:
    # 如果没有 sentence-transformers，默认使用 DashScope API
    EmbeddingService = DashScopeEmbedding

