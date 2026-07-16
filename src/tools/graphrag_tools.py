"""GraphRAG 知识图谱工具 - 为 Agent 提供图查询和推理能力"""

from typing import Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.config import settings
from src.graphrag.graph_store import Neo4jGraphStore
from src.graphrag.retriever import GraphRetriever


# === 全局懒初始化 ===

_graph_store: Optional[Neo4jGraphStore] = None
_graph_retriever: Optional[GraphRetriever] = None


def _get_retriever() -> GraphRetriever:
    """懒初始化图谱检索器（复用连接）"""
    global _graph_store, _graph_retriever
    if _graph_retriever is None:
        _graph_store = Neo4jGraphStore(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
            database=settings.NEO4J_DATABASE,
        )
        _graph_store.connect()
        _graph_retriever = GraphRetriever(_graph_store)
    return _graph_retriever


# === 输入模型 ===

class SymptomPathInput(BaseModel):
    symptom: str = Field(description="症状关键词，如「头痛」「咳嗽」「乏力」等")
    max_depth: int = Field(default=3, description="最大搜索深度，2=包含二度推理路径")


class GraphEntityInput(BaseModel):
    keyword: str = Field(description="搜索关键词，如实体名称、功效、适应症等")
    entity_type: Optional[str] = Field(
        default=None,
        description="实体类型：Formula(方剂)/Herb(药材)/Acupoint(穴位)/Constitution(体质)/Symptom(症状)/Meridian(经络)",
    )
    limit: int = Field(default=10, description="返回结果数量上限")


class GraphRelationInput(BaseModel):
    entity_name: str = Field(description="实体名称，如「麻黄汤」「人参」等")
    entity_type: Optional[str] = Field(
        default=None,
        description="实体类型：Formula/Herb/Acupoint/Constitution/Symptom/Meridian",
    )
    relation_type: Optional[str] = Field(
        default=None,
        description="关系类型：CONTAINS(包含) / TREATS(治疗) / BELONGS_TO(属于) / SOURCE_FROM(出自) / ENTERS_MERIDIAN(归经) / HAS_NATURE(药性)",
    )
    depth: int = Field(default=1, description="关系查询深度，1=直接关系，2=二度关系")


# === 工具类 ===

class SymptomPathTool(BaseTool):
    """症状→治疗路径推理工具"""

    name: str = "search_symptom_path"
    description: str = (
        "【知识图谱核心工具】根据症状发现治疗路径。"
        "通过图遍历返回：症状→方剂、症状→药材、症状→穴位、症状→体质、症状→方剂→药材 等多跳推理路径。"
        "当用户描述多个症状或需要综合分析时优先使用此工具。"
    )
    args_schema: Type[BaseModel] = SymptomPathInput

    def _run(self, symptom: str, max_depth: int = 3) -> str:
        retriever = _get_retriever()
        paths = retriever.find_treatment_path(symptom=symptom, max_depth=max_depth)
        if not paths:
            return f"知识图谱中未找到与「{symptom}」相关的治疗路径。"
        return retriever.format_context(paths)


class GraphEntitySearchTool(BaseTool):
    """图谱实体搜索工具"""

    name: str = "search_graph_entity"
    description: str = (
        "在知识图谱中搜索中医实体节点。"
        "支持按类型过滤（方剂Formula、药材Herb、穴位Acupoint、体质Constitution、症状Symptom、经络Meridian）。"
        "在实体的名称、功效、主治等字段中模糊匹配。"
    )
    args_schema: Type[BaseModel] = GraphEntityInput

    def _run(
        self,
        keyword: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        retriever = _get_retriever()
        entities = retriever.search_entities(
            keyword=keyword,
            entity_type=entity_type,
            limit=limit,
        )
        if not entities:
            type_hint = f"（类型：{entity_type}）" if entity_type else ""
            return f"知识图谱中未找到与「{keyword}」相关的实体{type_hint}。"

        lines = [f"找到 {len(entities)} 个相关实体：\n"]
        for e in entities:
            name = e["name"]
            etype = e["type"]
            props = e.get("properties", {})
            lines.append(f"【{name}】({etype})")

            # 按实体类型展示关键属性
            if etype == "Formula":
                if props.get("efficacy"):
                    lines.append(f"  功效：{props['efficacy']}")
                if props.get("composition"):
                    lines.append(f"  组成：{props['composition']}")
                if props.get("indications"):
                    lines.append(f"  主治：{props['indications']}")
                if props.get("contraindications"):
                    lines.append(f"  禁忌：{props['contraindications']}")
            elif etype == "Herb":
                if props.get("nature") and props.get("taste"):
                    lines.append(f"  性味：{props['nature']}，{props['taste']}")
                if props.get("meridian"):
                    lines.append(f"  归经：{props.get('meridian', '')}")
                if props.get("efficacy"):
                    lines.append(f"  功效：{props['efficacy']}")
                if props.get("dosage"):
                    lines.append(f"  用量：{props['dosage']}")
            elif etype == "Acupoint":
                if props.get("meridian"):
                    lines.append(f"  归经：{props.get('meridian', '')}")
                if props.get("location"):
                    lines.append(f"  定位：{props['location']}")
                if props.get("efficacy"):
                    lines.append(f"  功效：{props['efficacy']}")
            elif etype == "Constitution":
                if props.get("characteristics"):
                    lines.append(f"  特征：{props['characteristics'][:80]}...")
                if props.get("regulation"):
                    lines.append(f"  调理：{props['regulation']}")
            elif etype == "Symptom":
                pass  # 仅展示名称
            else:
                # 其他类型展示所有非内部属性
                for k, v in props.items():
                    if isinstance(v, str) and v:
                        lines.append(f"  {k}：{v[:100]}")
            lines.append("")
        return "\n".join(lines)


class GraphRelationTool(BaseTool):
    """图谱关系查询工具"""

    name: str = "search_graph_relation"
    description: str = (
        "查询知识图谱中实体间的关联关系。"
        "可查询方剂含哪些药材(CONTAINS)、药材归哪些经(ENTERS_MERIDIAN)、方剂/药材/穴位治疗哪些症状(TREATS)等。"
        "支持指定关系类型过滤，支持1度/2度关系查询。"
    )
    args_schema: Type[BaseModel] = GraphRelationInput

    def _run(
        self,
        entity_name: str,
        entity_type: Optional[str] = None,
        relation_type: Optional[str] = None,
        depth: int = 1,
    ) -> str:
        retriever = _get_retriever()

        if relation_type:
            # 按指定关系类型查找关联实体
            related = retriever.find_related_entities(
                entity_name=entity_name,
                relation_type=relation_type,
                limit=10,
            )
            if not related:
                return f"未找到「{entity_name}」的 {relation_type} 关联实体。"
            return self._format_related(entity_name, relation_type, related)

        # 获取完整关系视图
        relations = retriever.get_entity_relations(
            entity_name=entity_name,
            entity_type=entity_type,
            depth=depth,
        )
        return self._format_full(entity_name, relations)

    def _format_related(
        self,
        entity_name: str,
        relation_type: str,
        related: list,
    ) -> str:
        lines = [f"「{entity_name}」的 {relation_type} 关联实体：\n"]
        for r in related:
            lines.append(f"- {r['name']} ({r['type']})")
            props = r.get("properties", {})
            for k, v in props.items():
                if isinstance(v, str) and v and k not in ("name", "type"):
                    lines.append(f"    {k}：{v[:120]}")
                    break
        return "\n".join(lines)

    def _format_full(self, entity_name: str, relations: dict) -> str:
        outgoing = relations.get("outgoing", [])
        incoming = relations.get("incoming", [])
        paths = relations.get("paths", [])

        lines = [f"「{entity_name}」的关联关系：\n"]

        if outgoing:
            lines.append("【出边关系】")
            for r in outgoing:
                lines.append(f"  ──[{r['relation']}]──→ {r['target']}")
            lines.append("")

        if incoming:
            lines.append("【入边关系】")
            for r in incoming:
                lines.append(f"  {r['source']} ──[{r['relation']}]──→")
            lines.append("")

        if paths:
            lines.append("【二度路径】")
            for p in paths:
                l1 = p.get("level1", {})
                l2 = p.get("level2", {})
                lines.append(
                    f"  → {l1['name']} ──[{l1['relation']}]──→ {l2['name']}"
                )
            lines.append("")

        if not outgoing and not incoming and not paths:
            lines.append("（无关联关系）")

        return "\n".join(lines)


# === 工具获取函数 ===

def get_graphrag_tools() -> list:
    """获取所有 GraphRAG 知识图谱工具

    返回三个工具：
    - search_symptom_path: 症状→治疗路径多跳推理
    - search_graph_entity: 图谱实体搜索
    - search_graph_relation: 图谱关系查询
    """
    return [
        SymptomPathTool(),
        GraphEntitySearchTool(),
        GraphRelationTool(),
    ]
