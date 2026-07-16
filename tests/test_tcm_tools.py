"""P3 单元测试：结构化数据库工具（方剂、药材、穴位、体质）

使用 patch.object 注入 mock，避免 Pydantic 类型验证问题。
"""
import pytest
from unittest.mock import MagicMock, patch

from src.tools.tcm_tools import (
    FangjiSearchTool,
    HerbSearchTool,
    AcupointSearchTool,
    ConstitutionTool,
)


def _make_tool_with_mock_db(tool_cls, mock_db):
    """创建工具实例并用 patch.object 替换 db 为 mock"""
    tool = tool_cls()
    # 使用 object.__setattr__ 绕过 pydantic 验证
    object.__setattr__(tool, "db", mock_db)
    return tool


class TestFangjiSearchTool:
    """方剂查询工具测试"""

    def test_search_by_name(self, mock_db):
        """按方剂名搜索"""
        tool = _make_tool_with_mock_db(FangjiSearchTool, mock_db)
        result = tool._run(keyword="麻黄汤")

        assert "麻黄汤" in result
        assert "发汗解表" in result
        assert "解表剂" in result
        mock_db.search_fangji.assert_called_once_with(keyword="麻黄汤", category=None)

    def test_search_by_category(self, mock_db):
        """按分类过滤搜索"""
        tool = _make_tool_with_mock_db(FangjiSearchTool, mock_db)
        tool._run(keyword="解表", category="解表剂")

        mock_db.search_fangji.assert_called_once_with(keyword="解表", category="解表剂")

    def test_search_no_results(self, mock_empty_db):
        """搜索无结果"""
        tool = _make_tool_with_mock_db(FangjiSearchTool, mock_empty_db)
        result = tool._run(keyword="不存在的方剂")

        assert "未找到" in result

    def test_search_by_indication(self, mock_db):
        """按适应症搜索"""
        tool = _make_tool_with_mock_db(FangjiSearchTool, mock_db)
        result = tool._run(keyword="恶寒发热")

        assert "麻黄汤" in result or "找到" in result

    def test_format_includes_warnings(self, mock_db):
        """输出包含禁忌/注意事项"""
        mock_db.search_fangji.return_value = [
            {
                "name": "含附子方",
                "pinyin": "",
                "category": "温里剂",
                "ingredients": "附子10g 干姜6g",
                "usage": "先煎附子",
                "functions": "回阳救逆",
                "clinical_use": "亡阳证",
                "contraindications": "孕妇禁用",
                "precautions": "附子有毒，须先煎1小时",
                "adverse_reactions": "过量可致心律失常",
            }
        ]
        tool = _make_tool_with_mock_db(FangjiSearchTool, mock_db)
        result = tool._run(keyword="含附子方")

        assert "孕妇禁用" in result
        assert "附子有毒" in result
        assert "过量可致心律失常" in result


class TestHerbSearchTool:
    """药材查询工具测试"""

    def test_search_by_name(self, mock_db):
        """按药材名搜索"""
        tool = _make_tool_with_mock_db(HerbSearchTool, mock_db)
        result = tool._run(keyword="人参")

        assert "人参" in result
        assert "大补元气" in result
        assert "归脾、肺、心经" in result
        mock_db.search_herb.assert_called_once_with(keyword="人参", nature=None)

    def test_search_by_nature(self, mock_db):
        """按四气过滤搜索"""
        tool = _make_tool_with_mock_db(HerbSearchTool, mock_db)
        tool._run(keyword="补气", nature="温")

        mock_db.search_herb.assert_called_once_with(keyword="补气", nature="温")

    def test_search_no_results(self, mock_empty_db):
        """搜索无结果"""
        tool = _make_tool_with_mock_db(HerbSearchTool, mock_empty_db)
        result = tool._run(keyword="不存在的药材")

        assert "未找到" in result

    def test_toxicity_warning_present(self, mock_db):
        """毒性药材应包含注意事项"""
        mock_db.search_herb.return_value = [
            {
                "name": "附子",
                "latin_name": "Aconitum carmichaelii",
                "nature_taste_meridian": "大热。有毒",
                "functions": "回阳救逆",
                "usage": "3-15g",
                "source": "毛茛科",
                "processing": "炮制",
                "caution": "孕妇禁用。须先煎。",
            }
        ]
        tool = _make_tool_with_mock_db(HerbSearchTool, mock_db)
        result = tool._run(keyword="附子")

        assert "孕妇禁用" in result

    def test_format_displays_key_fields(self, mock_db):
        """输出应包含性味归经、功能主治等关键字段"""
        tool = _make_tool_with_mock_db(HerbSearchTool, mock_db)
        result = tool._run(keyword="人参")

        assert "性味归经" in result
        assert "功能主治" in result
        assert "来源" in result


class TestAcupointSearchTool:
    """穴位查询工具测试"""

    def test_search_by_name(self, mock_db):
        """按穴位名搜索"""
        tool = _make_tool_with_mock_db(AcupointSearchTool, mock_db)
        result = tool._run(keyword="足三里")

        assert "足三里" in result
        assert "足阳明胃经" in result
        assert "健脾和胃" in result
        mock_db.search_acupoint.assert_called_once_with(keyword="足三里")

    def test_search_no_results(self, mock_empty_db):
        """搜索无结果"""
        tool = _make_tool_with_mock_db(AcupointSearchTool, mock_empty_db)
        result = tool._run(keyword="不存在的穴位")

        assert "未找到" in result

    def test_format_shows_meridian_and_location(self, mock_db):
        """输出应包含归经和定位"""
        tool = _make_tool_with_mock_db(AcupointSearchTool, mock_db)
        result = tool._run(keyword="足三里")

        assert "归经" in result
        assert "定位" in result
        assert "主治" in result

    def test_pregnancy_warning(self, mock_db):
        """孕妇禁忌穴位应标注意"""
        mock_db.search_acupoint.return_value = [
            {
                "name": "合谷",
                "pinyin": "He Gu",
                "meridian": "手阳明大肠经",
                "location": "手背第1、2掌骨间",
                "method": "展掌取穴",
                "efficacy": "疏风解表",
                "indications": "头痛、牙痛",
                "technique": "直刺0.5-1寸",
                "cautions": "孕妇禁针",
            }
        ]
        tool = _make_tool_with_mock_db(AcupointSearchTool, mock_db)
        result = tool._run(keyword="合谷")

        assert "孕妇禁针" in result


class TestConstitutionTool:
    """体质查询工具测试"""

    def test_search_specific_type(self, mock_db):
        """查询特定体质"""
        tool = _make_tool_with_mock_db(ConstitutionTool, mock_db)
        result = tool._run(type_name="气虚质")

        assert "气虚质" in result
        assert "补气养气" in result
        assert "饮食建议" in result
        mock_db.get_constitution.assert_called_once_with("气虚质")

    def test_search_not_found(self, mock_empty_db):
        """查询不存在的体质"""
        tool = _make_tool_with_mock_db(ConstitutionTool, mock_empty_db)
        result = tool._run(type_name="不存在的体质")

        assert "未找到" in result

    def test_list_all_types(self, mock_db):
        """列出所有体质类型"""
        tool = _make_tool_with_mock_db(ConstitutionTool, mock_db)
        result = tool._run()

        assert "平和质" in result
        assert "气虚质" in result
        assert "阳虚质" in result
        mock_db.list_constitutions.assert_called_once()

    def test_empty_type_lists_all(self, mock_db):
        """type_name 为空时列出全部"""
        tool = _make_tool_with_mock_db(ConstitutionTool, mock_db)
        result = tool._run(type_name="")

        mock_db.list_constitutions.assert_called_once()
