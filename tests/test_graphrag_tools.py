"""P3 单元测试：知识图谱工具"""
import pytest
from unittest.mock import patch

from src.tools.graphrag_tools import (
    SymptomPathTool,
    GraphEntitySearchTool,
    GraphRelationTool,
    _get_retriever,
)


# 重置全局状态，避免测试间互相影响
@pytest.fixture(autouse=True)
def reset_global_graph_state():
    """每个测试前后重置全局 graph retriever 状态"""
    import src.tools.graphrag_tools as gtools

    gtools._graph_store = None
    gtools._graph_retriever = None
    yield
    gtools._graph_store = None
    gtools._graph_retriever = None


class TestSymptomPathTool:
    """症状路径推理工具测试"""

    def test_search_symptom_path(self, mock_graph_retriever):
        """搜索症状→治疗路径"""
        with patch.object(
            src.tools.graphrag_tools, "_get_retriever", return_value=mock_graph_retriever
        ):
            tool = SymptomPathTool()
            result = tool._run(symptom="头痛")

            assert "治疗路径" in result or "路径" in result or "麻黄汤" in result
            mock_graph_retriever.find_treatment_path.assert_called_once_with(
                symptom="头痛", max_depth=3
            )

    def test_custom_max_depth(self, mock_graph_retriever):
        """自定义搜索深度"""
        with patch.object(
            src.tools.graphrag_tools, "_get_retriever", return_value=mock_graph_retriever
        ):
            tool = SymptomPathTool()
            tool._run(symptom="咳嗽", max_depth=2)

            mock_graph_retriever.find_treatment_path.assert_called_once_with(
                symptom="咳嗽", max_depth=2
            )

    def test_no_path_found(self, mock_graph_retriever):
        """无治疗路径"""
        mock_graph_retriever.find_treatment_path.return_value = []
        with patch.object(
            src.tools.graphrag_tools, "_get_retriever", return_value=mock_graph_retriever
        ):
            tool = SymptomPathTool()
            result = tool._run(symptom="罕见症状")

            assert "未找到" in result


class TestGraphEntitySearchTool:
    """图谱实体搜索工具测试"""

    def test_search_entity_by_keyword(self, mock_graph_retriever):
        """按关键词搜索实体"""
        with patch.object(
            src.tools.graphrag_tools, "_get_retriever", return_value=mock_graph_retriever
        ):
            tool = GraphEntitySearchTool()
            result = tool._run(keyword="麻黄汤")

            assert "麻黄汤" in result
            assert "Formula" in result
            assert "发汗解表" in result
            mock_graph_retriever.search_entities.assert_called_once_with(
                keyword="麻黄汤", entity_type=None, limit=10
            )

    def test_search_with_type_filter(self, mock_graph_retriever):
        """按类型过滤搜索"""
        with patch.object(
            src.tools.graphrag_tools, "_get_retriever", return_value=mock_graph_retriever
        ):
            tool = GraphEntitySearchTool()
            tool._run(keyword="温", entity_type="Herb")

            mock_graph_retriever.search_entities.assert_called_once_with(
                keyword="温", entity_type="Herb", limit=10
            )

    def test_search_no_results(self, mock_graph_retriever):
        """无搜索结果"""
        mock_graph_retriever.search_entities.return_value = []
        with patch.object(
            src.tools.graphrag_tools, "_get_retriever", return_value=mock_graph_retriever
        ):
            tool = GraphEntitySearchTool()
            result = tool._run(keyword="不存在的实体")

            assert "未找到" in result

    def test_herb_entity_displays_properties(self, mock_graph_retriever):
        """药材实体展示性味归经等属性"""
        with patch.object(
            src.tools.graphrag_tools, "_get_retriever", return_value=mock_graph_retriever
        ):
            tool = GraphEntitySearchTool()
            result = tool._run(keyword="桂枝")

            assert "性味" in result or "Herb" in result


class TestGraphRelationTool:
    """图谱关系查询工具测试"""

    def test_get_full_relations(self, mock_graph_retriever):
        """查询完整关系视图"""
        with patch.object(
            src.tools.graphrag_tools, "_get_retriever", return_value=mock_graph_retriever
        ):
            tool = GraphRelationTool()
            result = tool._run(entity_name="麻黄汤")

            assert "关联" in result or "关系" in result
            mock_graph_retriever.get_entity_relations.assert_called_once_with(
                entity_name="麻黄汤", entity_type=None, depth=1
            )

    def test_search_by_relation_type(self, mock_graph_retriever):
        """按关系类型查询"""
        with patch.object(
            src.tools.graphrag_tools, "_get_retriever", return_value=mock_graph_retriever
        ):
            tool = GraphRelationTool()
            result = tool._run(
                entity_name="麻黄汤", relation_type="CONTAINS"
            )

            assert "CONTAINS" in result or "关联" in result or "桂枝" in result
            mock_graph_retriever.find_related_entities.assert_called_once_with(
                entity_name="麻黄汤", relation_type="CONTAINS", limit=10
            )

    def test_no_relations_found(self, mock_graph_retriever):
        """无关联关系"""
        mock_graph_retriever.get_entity_relations.return_value = {
            "outgoing": [],
            "incoming": [],
            "paths": [],
        }
        with patch.object(
            src.tools.graphrag_tools, "_get_retriever", return_value=mock_graph_retriever
        ):
            tool = GraphRelationTool()
            result = tool._run(entity_name="孤立实体")

            assert "无关联" in result or "关联" in result

    def test_depth_two_relations(self, mock_graph_retriever):
        """二度关系查询"""
        with patch.object(
            src.tools.graphrag_tools, "_get_retriever", return_value=mock_graph_retriever
        ):
            tool = GraphRelationTool()
            tool._run(entity_name="麻黄汤", depth=2)

            mock_graph_retriever.get_entity_relations.assert_called_once_with(
                entity_name="麻黄汤", entity_type=None, depth=2
            )


# 显式导入以解决 patch 引用问题
import src.tools.graphrag_tools  # noqa: E402
