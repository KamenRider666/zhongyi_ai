"""检索结果融合 — RRF (Reciprocal Rank Fusion) 算法"""

from typing import Dict, List


def rrf_fusion(
    dense_results: List[Dict],
    sparse_results: List[Dict],
    k: int = 60,
    top_k: int = 5,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
) -> List[Dict]:
    """Reciprocal Rank Fusion — 倒数排名融合

    将稠密检索和稀疏检索的结果按排名倒数求和融合，两路都命中的文档优先推荐。
    只看排名不看绝对分数，天然解决两路分数量纲不同的问题。

    Args:
        dense_results:  稠密向量检索结果列表（按相似度降序）
        sparse_results: 稀疏 BM25 检索结果列表（按 BM25 分数降序）
        k:              平滑常数（默认 60），降低高排名结果的权重差异
        top_k:          最终返回数量
        dense_weight:   稠密路权重（>1 提升语义匹配优先级）
        sparse_weight:  稀疏路权重（>1 提升关键词匹配优先级）

    Returns:
        融合排序后的 top_k 文档列表，每个文档额外包含 fused_score 字段

    Example:
        >>> dense = [{"content": "麻黄汤...", "score": 0.9}, ...]
        >>> sparse = [{"content": "桂枝汤...", "score": 12.3}, ...]
        >>> fused = rrf_fusion(dense, sparse, top_k=5)
    """
    scores: Dict[str, float] = {}
    doc_map: Dict[str, Dict] = {}

    # 稠密路
    for rank, doc in enumerate(dense_results, 1):
        key = _doc_key(doc)
        scores[key] = scores.get(key, 0.0) + dense_weight / (k + rank)
        if key not in doc_map:
            doc_map[key] = doc

    # 稀疏路
    for rank, doc in enumerate(sparse_results, 1):
        key = _doc_key(doc)
        scores[key] = scores.get(key, 0.0) + sparse_weight / (k + rank)
        if key not in doc_map:
            doc_map[key] = doc

    # 按融合分数降序排序
    ranked = sorted(scores.items(), key=lambda x: -x[1])

    results: List[Dict] = []
    for key, score in ranked[:top_k]:
        doc = doc_map[key].copy()
        doc["fused_score"] = round(score, 6)
        results.append(doc)

    return results


def _doc_key(doc: Dict) -> str:
    """生成文档去重 key（取 content 前 100 字符，避免全文比较）"""
    content = doc.get("content", "")
    if isinstance(content, str):
        return content[:100]
    return str(content)[:100]
