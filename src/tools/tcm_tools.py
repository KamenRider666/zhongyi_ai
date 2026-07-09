"""LangChain 工具定义 - 方剂、药材、穴位查询"""

from typing import Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.data.database import TCMDatabase
from src.tools.graphrag_tools import get_graphrag_tools


# === 工具输入模型 ===

class FangjiSearchInput(BaseModel):
    keyword: str = Field(description="搜索关键词，如方剂名称、适应症、功效等")
    category: Optional[str] = Field(default=None, description="方剂分类：解表剂/补益剂/和解剂/祛痰剂/祛湿剂等")


class HerbSearchInput(BaseModel):
    keyword: str = Field(description="搜索关键词，如药材名称、功效、适应症等")
    nature: Optional[str] = Field(default=None, description="四气：寒/热/温/凉/平")


class AcupointSearchInput(BaseModel):
    keyword: str = Field(description="搜索关键词，如穴位名称、适应症、所属经络等")


class ConstitutionInput(BaseModel):
    type_name: Optional[str] = Field(default=None, description="体质类型名称，留空则列出所有体质")


# === 工具类 ===

class FangjiSearchTool(BaseTool):
    """方剂查询工具"""
    name: str = "search_fangji"
    description: str = (
        "查询中医方剂信息。根据关键词搜索方剂的名称、组成、功效、适应症、用法用量等。"
        "支持按分类过滤（如解表剂、补益剂等）。"
    )
    args_schema: Type[BaseModel] = FangjiSearchInput

    db: TCMDatabase = Field(default_factory=lambda: TCMDatabase())

    def _run(self, keyword: str, category: Optional[str] = None) -> str:
        results = self.db.search_fangji(keyword=keyword, category=category)
        if not results:
            return f"未找到与「{keyword}」相关的方剂。"
        return self._format(results)

    def _format(self, results: list) -> str:
        lines = [f"找到 {len(results)} 条相关方剂：\n"]
        for r in results:
            lines.append(f"【{r['name']}】")
            lines.append(f"  出处：{r['source']}")
            lines.append(f"  分类：{r['category']}")
            lines.append(f"  组成：{r['composition']}")
            lines.append(f"  用法：{r.get('usage_method', '')}")
            lines.append(f"  功效：{r['efficacy']}")
            lines.append(f"  主治：{r['indications']}")
            if r.get('contraindications'):
                lines.append(f"  禁忌：{r['contraindications']}")
            if r.get('notes'):
                lines.append(f"  备注：{r['notes']}")
            lines.append("")
        return "\n".join(lines)


class HerbSearchTool(BaseTool):
    """药材查询工具"""
    name: str = "search_herb"
    description: str = (
        "查询中药材信息。根据关键词搜索药材的性味归经、功效主治、用法用量、毒性禁忌等。"
        "支持按四气（寒热温凉平）过滤。"
    )
    args_schema: Type[BaseModel] = HerbSearchInput

    db: TCMDatabase = Field(default_factory=lambda: TCMDatabase())

    def _run(self, keyword: str, nature: Optional[str] = None) -> str:
        results = self.db.search_herb(keyword=keyword, nature=nature)
        if not results:
            return f"未找到与「{keyword}」相关的药材。"
        return self._format(results)

    def _format(self, results: list) -> str:
        lines = [f"找到 {len(results)} 条相关药材：\n"]
        for r in results:
            lines.append(f"【{r['name']}】{r.get('latin_name', '')}")
            lines.append(f"  性味：{r['nature']}，{r['taste']}")
            lines.append(f"  归经：{r['meridian']}")
            lines.append(f"  功效：{r['efficacy']}")
            lines.append(f"  主治：{r['indications']}")
            lines.append(f"  用量：{r.get('dosage', '')}")
            if r.get('toxicity') and r['toxicity'] != '无毒':
                lines.append(f"  ⚠ 毒性：{r['toxicity']}")
            if r.get('contraindications'):
                lines.append(f"  禁忌：{r['contraindications']}")
            lines.append("")
        return "\n".join(lines)


class AcupointSearchTool(BaseTool):
    """穴位查询工具"""
    name: str = "search_acupoint"
    description: str = "查询中医穴位信息。根据关键词搜索穴位的定位、功效、主治、操作手法等。"
    args_schema: Type[BaseModel] = AcupointSearchInput

    db: TCMDatabase = Field(default_factory=lambda: TCMDatabase())

    def _run(self, keyword: str) -> str:
        results = self.db.search_acupoint(keyword=keyword)
        if not results:
            return f"未找到与「{keyword}」相关的穴位。"
        return self._format(results)

    def _format(self, results: list) -> str:
        lines = [f"找到 {len(results)} 条相关穴位：\n"]
        for r in results:
            lines.append(f"【{r['name']}】{r.get('pinyin', '')}")
            lines.append(f"  归经：{r['meridian']}")
            lines.append(f"  定位：{r['location']}")
            lines.append(f"  取穴法：{r.get('method', '')}")
            lines.append(f"  功效：{r['efficacy']}")
            lines.append(f"  主治：{r['indications']}")
            if r.get('technique'):
                lines.append(f"  操作：{r['technique']}")
            if r.get('cautions'):
                lines.append(f"  ⚠ 注意：{r['cautions']}")
            lines.append("")
        return "\n".join(lines)


class ConstitutionTool(BaseTool):
    """体质查询工具"""
    name: str = "search_constitution"
    description: str = "查询中医体质类型信息。可查询九种体质的特征、调理方法、饮食建议等。不传参数则列出所有体质类型。"
    args_schema: Type[BaseModel] = ConstitutionInput

    db: TCMDatabase = Field(default_factory=lambda: TCMDatabase())

    def _run(self, type_name: Optional[str] = None) -> str:
        if type_name:
            result = self.db.get_constitution(type_name)
            if not result:
                return f"未找到体质类型「{type_name}」。可查询：平和质、气虚质、阳虚质、阴虚质、痰湿质、湿热质、血瘀质、气郁质、特禀质"
            return self._format_one(result)

        results = self.db.list_constitutions()
        lines = ["中医九种体质类型：\n"]
        for r in results:
            lines.append(f"- {r['type_name']}：{r['characteristics'][:50]}...")
        lines.append("\n输入具体体质名称可查看详细调理方案。")
        return "\n".join(lines)

    def _format_one(self, r: dict) -> str:
        return f"""【{r['type_name']}】

特征：{r['characteristics']}

易患倾向：{r.get('tendency', '')}

调理原则：{r['regulation']}

饮食建议：{r.get('diet_advice', '')}

运动建议：{r.get('exercise_advice', '')}

穴位建议：{r.get('acupoint_advice', '')}"""


def get_all_tools() -> list:
    """获取所有可用工具（含知识图谱工具）"""
    return [
        FangjiSearchTool(),
        HerbSearchTool(),
        AcupointSearchTool(),
        ConstitutionTool(),
    ] + get_graphrag_tools()
