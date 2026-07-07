"""向量嵌入服务 - 使用 sentence-transformers"""

from typing import List

from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """文本向量化服务"""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: List[str]) -> List[List[float]]:
        """将文本列表转换为向量"""
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def encode_query(self, query: str) -> List[float]:
        """将查询文本转换为向量"""
        embedding = self.model.encode(query, normalize_embeddings=True)
        return embedding.tolist()
