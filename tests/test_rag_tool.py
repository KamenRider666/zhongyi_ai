"""P3 单元测试：RAG 语义检索工具

使用 object.__setattr__ 注入 mock，绕过 Pydantic 类型验证。
"""
import pytest
from unittest.mock import MagicMock

from src.tools.rag_tool import TCMKnowledgeSearchTool


def _make_tool_with_mock_retriever(mock_retriever):
    """创建工具并用 object.__setattr__ 替换 retriever 为 mock"""
    tool = TCMKnowledgeSearchTool()
    object.__setattr__(tool, "retriever", mock_retriever)
    return tool


class TestTCMKnowledgeSearchTool:
    """RAG 语义检索工具测试"""

    def test_search_returns_formatted_results(self, mock_retriever):
        """语义搜索返回格式化结果"""
        tool = _make_tool_with_mock_retriever(mock_retriever)
        result = tool._run(query="活血化瘀")

        assert "四物汤" in result or "相关" in result or "活血" in result
        mock_retriever.retrieve.assert_called_once_with(query="活血化瘀", top_k=5)

    def test_search_with_custom_top_k(self, mock_retriever):
        """自定义返回数量"""
        tool = _make_tool_with_mock_retriever(mock_retriever)
        tool._run(query="补气养血", top_k=3)

        mock_retriever.retrieve.assert_called_once_with(query="补气养血", top_k=3)

    def test_search_no_results(self, mock_retriever):
        """无搜索结果"""
        mock_retriever.retrieve.return_value = []
        tool = _make_tool_with_mock_retriever(mock_retriever)
        result = tool._run(query="不存在的查询")

        assert "未找到" in result

    def test_search_handles_exception(self, mock_retriever):
        """检索异常处理"""
        mock_retriever.retrieve.side_effect = RuntimeError("向量库连接失败")
        tool = _make_tool_with_mock_retriever(mock_retriever)
        result = tool._run(query="活血化瘀")

        assert "检索失败" in result or "失败" in result

    def test_semantic_vs_keyword_distinction(self, mock_retriever):
        """语义搜索与关键词搜索的区分：模糊描述也能匹配"""
        tool = _make_tool_with_mock_retriever(mock_retriever)
        tool._run(query="血液流通不畅")

        mock_retriever.retrieve.assert_called_once_with(query="血液流通不畅", top_k=5)

    def test_default_top_k_is_five(self, mock_retriever):
        """默认 top_k 为 5"""
        tool = _make_tool_with_mock_retriever(mock_retriever)
        tool._run(query="补中益气")

        mock_retriever.retrieve.assert_called_once_with(query="补中益气", top_k=5)
