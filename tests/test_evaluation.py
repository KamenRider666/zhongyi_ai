"""P3 黑盒评测：Agent 回答质量评估"""
import pytest

from src.agent.core import TCM_SYSTEM_PROMPT
from src.tools.tcm_tools import (
    FangjiSearchTool,
    HerbSearchTool,
    AcupointSearchTool,
    ConstitutionTool,
)
from src.tools.rag_tool import TCMKnowledgeSearchTool
from src.tools.graphrag_tools import (
    SymptomPathTool,
    GraphEntitySearchTool,
    GraphRelationTool,
)


# ============================================================
#  20 条典型中医问诊测试用例（文档级对照）
# ============================================================

TCM_QUERIES = [
    ("麻黄汤的组成", "方剂组成"),
    ("活血化瘀的方剂有哪些", "活血化瘀方剂推荐"),
    ("四物汤的禁忌症是什么", "禁忌信息"),
    ("解表剂有哪些方子", "分类查询"),
    ("桂枝汤和麻黄汤的区别", "方剂比较"),
    ("人参的功效", "药材功效"),
    ("治疗咳嗽的中药", "症状→药材推理"),
    ("附子的毒性", "毒性警示"),
    ("当归的用法用量", "专业知识深度"),
    ("寒性药材有哪些", "药材属性查询"),
    ("头痛按什么穴位", "穴位推荐"),
    ("足三里的位置", "穴位定位"),
    ("太冲穴属于哪条经络", "经络知识"),
    ("孕妇可以艾灸哪些穴位", "特殊人群禁忌"),
    ("经常手脚冰凉是怎么回事", "体质辨识"),
    ("晚上失眠多梦怎么办", "辨证能力"),
    ("我最近总是口干舌燥、容易上火", "多症状综合分析"),
    ("夏天应该怎么养生", "养生建议"),
    ("气滞血瘀有什么症状", "病因病机分析"),
    ("老年人补气血喝什么汤", "调护建议"),
]


class TestToolDescriptions:
    """工具描述质量检查"""

    def test_fangji_tool_has_clear_description(self):
        tool = FangjiSearchTool()
        assert "方剂" in tool.description

    def test_herb_tool_has_toxicity_hint(self):
        tool = HerbSearchTool()
        desc = tool.description + str(tool.args_schema.model_json_schema())
        assert "毒性" in desc or "禁忌" in desc or "四气" in desc

    def test_constitution_tool_lists_all_types(self, mock_db):
        """列出所有 9 种体质"""
        import src.tools.tcm_tools as tcm
        # injection: bypass pydantic 验证
        tool = ConstitutionTool()
        object.__setattr__(tool, "db", mock_db)
        result = tool._run()

        for body_type in [
            "平和质", "气虚质", "阳虚质", "阴虚质",
            "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质",
        ]:
            assert body_type in result, f"体质列表中缺少 {body_type}"

    def test_rag_tool_semantic_explanation(self):
        tool = TCMKnowledgeSearchTool()
        assert "语义" in tool.description
        assert "向量" in tool.description or "相似度" in tool.description

    def test_symptom_path_tool_multihop(self):
        tool = SymptomPathTool()
        assert "路径" in tool.description or "多跳" in tool.description

    def test_all_tools_have_unique_names(self):
        """所有工具名称必须唯一（排除需要外部服务的 RAG/Graph 工具）"""
        tools = [
            FangjiSearchTool(),
            HerbSearchTool(),
            AcupointSearchTool(),
            ConstitutionTool(),
        ]
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), f"工具名称重复: {names}"


class TestEvaluationCriteria:
    """评估标准检查 — System Prompt 覆盖所有质量指标"""

    def test_sp_contains_differential_diagnosis(self):
        assert "辨证论治" in TCM_SYSTEM_PROMPT or "八纲辨证" in TCM_SYSTEM_PROMPT

    def test_sp_contains_formula_requirements(self):
        assert "出处" in TCM_SYSTEM_PROMPT or "组成" in TCM_SYSTEM_PROMPT

    def test_sp_contains_toxicity_warning(self):
        assert "有毒" in TCM_SYSTEM_PROMPT or "毒性" in TCM_SYSTEM_PROMPT
        assert "警告" in TCM_SYSTEM_PROMPT or "标注" in TCM_SYSTEM_PROMPT

    def test_sp_contains_emergency_handling(self):
        assert "立即就医" in TCM_SYSTEM_PROMPT or "急重症" in TCM_SYSTEM_PROMPT
        assert any(kw in TCM_SYSTEM_PROMPT for kw in ["胸痛", "高热", "昏迷", "大出血"])

    def test_sp_contains_dosage_warning(self):
        assert "医师指导" in TCM_SYSTEM_PROMPT or "请在医师" in TCM_SYSTEM_PROMPT

    def test_sp_has_structured_answer_format(self):
        assert "辨证分析" in TCM_SYSTEM_PROMPT
        assert "方药推荐" in TCM_SYSTEM_PROMPT
        assert "调护建议" in TCM_SYSTEM_PROMPT

    def test_sp_contains_classical_references(self):
        classics = ["黄帝内经", "伤寒论", "金匮要略", "本草纲目", "神农本草经"]
        assert any(c in TCM_SYSTEM_PROMPT for c in classics), (
            f"System Prompt 缺少中医经典引用"
        )

    def test_sp_contains_disclaimer(self):
        assert "免责" in TCM_SYSTEM_PROMPT or "仅供参考" in TCM_SYSTEM_PROMPT

    def test_sp_keyword_coverage(self):
        """关键术语覆盖检查"""
        coverage_keywords = [
            "方剂", "药材", "穴位", "体质", "辨证", "禁忌", "养生", "调护", "症状",
        ]
        for kw in coverage_keywords:
            assert kw in TCM_SYSTEM_PROMPT, f"System Prompt 缺少关键词: {kw}"

    def test_query_categories_in_sp(self):
        """20 条用例的核心场景在 System Prompt 中均有对应指引"""
        # 这些场景类型必须在 SP 中有描述
        assert "方剂推荐" in TCM_SYSTEM_PROMPT or "方剂" in TCM_SYSTEM_PROMPT
        assert "体质辨识" in TCM_SYSTEM_PROMPT
        assert "药材知识" in TCM_SYSTEM_PROMPT
        assert "穴位推荐" in TCM_SYSTEM_PROMPT
        assert "养生建议" in TCM_SYSTEM_PROMPT


class TestFullToolCoverage:
    """完整工具覆盖测试"""

    def test_all_eight_tools_registered(self):
        """验证 8 个工具全部注册"""
        from src.tools.tcm_tools import get_all_tools

        tools = get_all_tools()
        assert len(tools) == 8, f"预期 8 个工具，实际 {len(tools)} 个"

        tool_names = [t.name for t in tools]
        expected_names = [
            "search_fangji",
            "search_herb",
            "search_acupoint",
            "search_constitution",
            "search_tcm_knowledge",
            "search_symptom_path",
            "search_graph_entity",
            "search_graph_relation",
        ]
        for name in expected_names:
            assert name in tool_names, f"缺少工具: {name}"
