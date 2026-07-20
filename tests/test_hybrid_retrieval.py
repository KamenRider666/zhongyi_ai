"""混合检索单元测试：RRF 融合算法 + BM25 稀疏检索"""

import pytest
from unittest.mock import MagicMock, patch

from src.rag.fusion import rrf_fusion, _doc_key
from src.rag.bm25_store import BM25Store


# ═══════════════════════════════════════════════
#  RRF 融合算法测试
# ═══════════════════════════════════════════════

class TestRRFFusion:
    """RRF 倒数排名融合测试"""

    def test_both_paths_hit_ranks_higher(self):
        """两路都命中的文档应该排名高于单路命中"""
        dense = [
            {"content": "文档A（仅稠密命中）", "score": 0.9},
            {"content": "文档B（两路都命中）", "score": 0.8},
        ]
        sparse = [
            {"content": "文档B（两路都命中）", "score": 12.0},
            {"content": "文档C（仅稀疏命中）", "score": 8.0},
        ]

        fused = rrf_fusion(dense, sparse, top_k=3)

        # 文档B在稠密排第2、稀疏排第1，融合分应最高
        assert fused[0]["content"] == "文档B（两路都命中）"
        assert "fused_score" in fused[0]

    def test_single_path_only(self):
        """单路有结果时正常返回"""
        dense = [
            {"content": "文档1", "score": 0.9},
            {"content": "文档2", "score": 0.7},
        ]
        sparse = []

        fused = rrf_fusion(dense, sparse, top_k=2)

        assert len(fused) == 2
        assert fused[0]["content"] == "文档1"

    def test_empty_inputs(self):
        """空输入返回空列表"""
        assert rrf_fusion([], [], top_k=5) == []

    def test_top_k_limit(self):
        """top_k 限制返回数量"""
        dense = [{"content": f"文档{i}", "score": 0.9 - i * 0.1} for i in range(10)]
        sparse = [{"content": f"文档{i}", "score": 10 - i} for i in range(10)]

        fused = rrf_fusion(dense, sparse, top_k=3)

        assert len(fused) == 3

    def test_weight_adjustment(self):
        """权重调整：提升稀疏权重时，仅稀疏命中的文档排名上升"""
        dense = [{"content": "仅稠密", "score": 0.9}]
        sparse = [{"content": "仅稀疏", "score": 10.0}]

        # 稠密权重远大于稀疏
        fused_dense_heavy = rrf_fusion(
            dense, sparse, top_k=2, dense_weight=10.0, sparse_weight=0.1
        )
        assert fused_dense_heavy[0]["content"] == "仅稠密"

        # 稀疏权重远大于稠密
        fused_sparse_heavy = rrf_fusion(
            dense, sparse, top_k=2, dense_weight=0.1, sparse_weight=10.0
        )
        assert fused_sparse_heavy[0]["content"] == "仅稀疏"

    def test_fused_score_is_float(self):
        """融合分数为浮点数"""
        dense = [{"content": "文档A", "score": 0.9}]
        sparse = [{"content": "文档B", "score": 10.0}]

        fused = rrf_fusion(dense, sparse, top_k=2)

        for doc in fused:
            assert isinstance(doc["fused_score"], float)

    def test_doc_key_dedup(self):
        """相同内容去重（不重复计入）"""
        same_content = "这是一段相同的内容用于测试去重"
        dense = [{"content": same_content, "score": 0.9}]
        sparse = [{"content": same_content, "score": 10.0}]

        fused = rrf_fusion(dense, sparse, top_k=5)

        assert len(fused) == 1  # 去重后只有1条


# ═══════════════════════════════════════════════
#  BM25 稀疏检索测试
# ═══════════════════════════════════════════════

class TestBM25Store:
    """BM25 内存索引测试"""

    def test_tokenize_chinese(self):
        """jieba 中文分词"""
        tokens = BM25Store._tokenize("麻黄汤治疗风寒感冒")
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        # "麻黄汤" 应该被识别为一个词（自定义词典）
        assert "麻黄汤" in tokens

    def test_tokenize_filters_punctuation(self):
        """标点符号被过滤"""
        tokens = BM25Store._tokenize("活血化瘀，清热解毒。")
        assert "，" not in tokens
        assert "。" not in tokens
        assert "活血化瘀" in tokens

    def test_tokenize_empty_string(self):
        """空字符串返回空列表"""
        assert BM25Store._tokenize("") == []

    def test_search_empty_store(self):
        """空索引检索返回空列表"""
        store = BM25Store()
        # 未构建索引，is_ready 为 False
        assert not store.is_ready
        assert store.search("麻黄汤") == []

    def test_build_and_search(self):
        """构建索引并检索"""
        store = BM25Store()

        # 模拟 QdrantStore
        mock_qdrant = MagicMock()
        mock_qdrant.scroll_all.return_value = [
            {"content": "【方名】麻黄汤\n【组成】麻黄 桂枝 杏仁 甘草\n【功能主治】发汗解表，宣肺平喘", "source": "formulas", "category": "formula"},
            {"content": "【方名】桂枝汤\n【组成】桂枝 芍药 甘草 生姜 大枣\n【功能主治】解肌发表，调和营卫", "source": "formulas", "category": "formula"},
            {"content": "【药名】麻黄\n【性味归经】辛、微苦，温。归肺、膀胱经\n【功能主治】发汗解表，宣肺平喘", "source": "herbs", "category": "herb"},
            {"content": "【药名】当归\n【性味归经】甘、辛，温。归肝、心、脾经\n【功能主治】补血活血，调经止痛", "source": "herbs", "category": "herb"},
        ]

        count = store.build_from_qdrant(mock_qdrant)

        assert count == 4
        assert store.is_ready

        # 搜索"麻黄汤"应该精确命中
        results = store.search("麻黄汤", top_k=5)
        assert len(results) > 0
        # 第一条应该是麻黄汤（精确匹配）
        assert "麻黄汤" in results[0]["content"]

    def test_search_with_category_filter(self):
        """分类过滤"""
        store = BM25Store()

        mock_qdrant = MagicMock()
        mock_qdrant.scroll_all.return_value = [
            {"content": "【方名】麻黄汤\n发汗解表", "source": "formulas", "category": "formula"},
            {"content": "【药名】麻黄\n发汗解表，宣肺平喘", "source": "herbs", "category": "herb"},
        ]

        store.build_from_qdrant(mock_qdrant)

        # 只搜索方剂分类
        results = store.search("发汗", top_k=5, category="formula")
        assert all(r["category"] == "formula" for r in results)

    def test_search_no_match(self):
        """无匹配返回空列表"""
        store = BM25Store()

        mock_qdrant = MagicMock()
        mock_qdrant.scroll_all.return_value = [
            {"content": "【方名】麻黄汤\n发汗解表", "source": "formulas", "category": "formula"},
        ]

        store.build_from_qdrant(mock_qdrant)

        results = store.search("量子力学", top_k=5)
        assert results == []


# ═══════════════════════════════════════════════
#  混合检索器集成测试
# ═══════════════════════════════════════════════

class TestHybridRetriever:
    """TCMRetriever 混合检索集成测试"""

    def test_hybrid_retrieval_uses_both_paths(self):
        """混合检索同时调用稠密和稀疏"""
        from src.rag.retriever import TCMRetriever

        mock_vector_store = MagicMock()
        mock_vector_store.search.return_value = [
            {"content": "稠密结果1", "source": "test", "category": "formula", "score": 0.9},
            {"content": "稠密结果2", "source": "test", "category": "formula", "score": 0.7},
        ]

        mock_embedding = MagicMock()
        mock_embedding.encode_query.return_value = [0.1] * 1024

        mock_bm25 = MagicMock()
        mock_bm25.is_ready = True
        mock_bm25.search.return_value = [
            {"content": "稀疏结果1", "source": "test", "category": "formula", "score": 10.0},
            {"content": "稠密结果1", "source": "test", "category": "formula", "score": 8.0},
        ]

        retriever = TCMRetriever(
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
            bm25_store=mock_bm25,
        )

        results = retriever.retrieve("麻黄汤", top_k=3)

        # 两路都被调用
        mock_vector_store.search.assert_called_once()
        mock_bm25.search.assert_called_once()

        # 结果经过 RRF 融合
        assert len(results) <= 3
        # "稠密结果1"在两路都出现，应排第一
        assert results[0]["content"] == "稠密结果1"

    def test_fallback_to_dense_when_bm25_none(self):
        """BM25 为 None 时退化为纯稠密"""
        from src.rag.retriever import TCMRetriever

        mock_vector_store = MagicMock()
        mock_vector_store.search.return_value = [
            {"content": "稠密结果1", "source": "test", "category": "formula", "score": 0.9},
        ]

        mock_embedding = MagicMock()
        mock_embedding.encode_query.return_value = [0.1] * 1024

        retriever = TCMRetriever(
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
            bm25_store=None,  # 无 BM25
        )

        results = retriever.retrieve("活血化瘀", top_k=5)

        mock_vector_store.search.assert_called_once()
        assert len(results) == 1

    def test_fallback_to_dense_when_bm25_empty(self):
        """BM25 无结果时退化为纯稠密"""
        from src.rag.retriever import TCMRetriever

        mock_vector_store = MagicMock()
        mock_vector_store.search.return_value = [
            {"content": "稠密结果1", "source": "test", "category": "formula", "score": 0.9},
        ]

        mock_embedding = MagicMock()
        mock_embedding.encode_query.return_value = [0.1] * 1024

        mock_bm25 = MagicMock()
        mock_bm25.is_ready = True
        mock_bm25.search.return_value = []  # BM25 无结果

        retriever = TCMRetriever(
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
            bm25_store=mock_bm25,
        )

        results = retriever.retrieve("量子力学", top_k=5)

        # BM25 无结果，退化到纯稠密
        assert len(results) == 1
        assert results[0]["content"] == "稠密结果1"
