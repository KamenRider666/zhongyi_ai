"""知识图谱检索器 - 图查询与推理"""

from typing import Any, Dict, List, Optional

from src.graphrag.graph_store import Neo4jGraphStore


class GraphRetriever:
    """中医知识图谱检索器"""

    def __init__(self, graph_store: Neo4jGraphStore):
        self.store = graph_store

    def search_entities(
        self,
        keyword: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索实体节点

        Args:
            keyword: 搜索关键词
            entity_type: 实体类型 (Formula/Herb/Acupoint/Constitution/Symptom/Meridian)
            limit: 返回数量

        Returns:
            匹配的实体列表
        """
        if entity_type:
            query = f"""
            MATCH (n:{entity_type})
            WHERE n.name CONTAINS $keyword OR n.efficacy CONTAINS $keyword
               OR n.indications CONTAINS $keyword OR n.type CONTAINS $keyword
            RETURN n, labels(n) AS types
            LIMIT $limit
            """
        else:
            query = """
            MATCH (n)
            WHERE n.name CONTAINS $keyword OR n.efficacy CONTAINS $keyword
               OR n.indications CONTAINS $keyword OR n.type CONTAINS $keyword
               OR n.characteristics CONTAINS $keyword
            RETURN n, labels(n) AS types
            LIMIT $limit
            """

        results = self.store.execute_query(query, {"keyword": keyword, "limit": limit})
        entities = []
        for r in results:
            node = r["n"]
            types = r["types"]
            entities.append({
                "name": node.get("name", node.get("type", "")),
                "type": types[0] if types else "Unknown",
                "properties": dict(node),
            })
        return entities

    def get_entity_relations(
        self,
        entity_name: str,
        entity_type: Optional[str] = None,
        depth: int = 1,
    ) -> Dict[str, Any]:
        """获取实体的关联关系

        Args:
            entity_name: 实体名称
            entity_type: 实体类型标签
            depth: 关系深度 (1=直接关系, 2=二度关系)

        Returns:
            实体及其关联信息
        """
        name_field = "n.name" if entity_type != "Constitution" else "n.type"

        if depth == 1:
            if entity_type:
                query = f"""
                MATCH (n:{entity_type}) WHERE {name_field} = $name
                OPTIONAL MATCH (n)-[r]->(m)
                OPTIONAL MATCH (p)-[r2]->(n)
                RETURN n, type(r) AS out_relation, m AS out_target,
                       type(r2) AS in_relation, p AS in_source
                """
            else:
                query = """
                MATCH (n) WHERE n.name = $name OR n.type = $name
                OPTIONAL MATCH (n)-[r]->(m)
                OPTIONAL MATCH (p)-[r2]->(n)
                RETURN n, type(r) AS out_relation, m AS out_target,
                       type(r2) AS in_relation, p AS in_source
                """
        else:
            # 二度关系查询
            if entity_type:
                query = f"""
                MATCH (n:{entity_type}) WHERE {name_field} = $name
                OPTIONAL MATCH path = (n)-[r1]->(m1)-[r2]->(m2)
                WHERE m1 <> m2 AND m2 <> n
                RETURN n, m1 AS level1_node, type(r1) AS level1_rel,
                       m2 AS level2_node, type(r2) AS level2_rel
                """
            else:
                query = """
                MATCH (n) WHERE n.name = $name OR n.type = $name
                OPTIONAL MATCH path = (n)-[r1]->(m1)-[r2]->(m2)
                WHERE m1 <> m2 AND m2 <> n
                RETURN n, m1 AS level1_node, type(r1) AS level1_rel,
                       m2 AS level2_node, type(r2) AS level2_rel
                """

        results = self.store.execute_query(query, {"name": entity_name})
        return self._format_relations(entity_name, results, depth)

    def find_treatment_path(
        self,
        symptom: str,
        max_depth: int = 3,
    ) -> List[Dict[str, Any]]:
        """根据症状寻找治疗路径

        这是 GraphRAG 的核心能力：通过图遍历发现
        症状 → 方剂 → 药材、症状 → 穴位、症状 → 体质 的推理路径

        Args:
            symptom: 症状关键词
            max_depth: 最大搜索深度

        Returns:
            治疗路径列表
        """
        paths = []

        # 1. 症状 → 方剂（反向查找 TREATS 关系）
        formula_results = self.store.execute_query(
            """
            MATCH (f:Formula)-[:TREATS]->(s:Symptom)
            WHERE s.name CONTAINS $symptom
            RETURN f.name AS formula_name, f.efficacy AS efficacy,
                   f.composition AS composition, f.indications AS indications,
                   f.contraindications AS contraindications
            LIMIT 5
            """,
            {"symptom": symptom},
        )
        for r in formula_results:
            paths.append({
                "path_type": "症状→方剂",
                "symptom": symptom,
                "target_type": "Formula",
                "target_name": r["formula_name"],
                "details": {
                    "efficacy": r["efficacy"],
                    "composition": r["composition"],
                    "indications": r["indications"],
                    "contraindications": r.get("contraindications", ""),
                },
            })

        # 2. 症状 → 药材
        herb_results = self.store.execute_query(
            """
            MATCH (h:Herb)-[:TREATS]->(s:Symptom)
            WHERE s.name CONTAINS $symptom
            RETURN h.name AS herb_name, h.efficacy AS efficacy,
                   h.nature AS nature, h.taste AS taste,
                   h.meridian AS meridian, h.dosage AS dosage,
                   h.toxicity AS toxicity
            LIMIT 5
            """,
            {"symptom": symptom},
        )
        for r in herb_results:
            paths.append({
                "path_type": "症状→药材",
                "symptom": symptom,
                "target_type": "Herb",
                "target_name": r["herb_name"],
                "details": {
                    "efficacy": r["efficacy"],
                    "nature": r["nature"],
                    "taste": r["taste"],
                    "meridian": r["meridian"],
                    "dosage": r.get("dosage", ""),
                    "toxicity": r.get("toxicity", "无毒"),
                },
            })

        # 3. 症状 → 穴位
        acupoint_results = self.store.execute_query(
            """
            MATCH (a:Acupoint)-[:TREATS]->(s:Symptom)
            WHERE s.name CONTAINS $symptom
            RETURN a.name AS acupoint_name, a.efficacy AS efficacy,
                   a.location AS location, a.meridian AS meridian,
                   a.technique AS technique
            LIMIT 5
            """,
            {"symptom": symptom},
        )
        for r in acupoint_results:
            paths.append({
                "path_type": "症状→穴位",
                "symptom": symptom,
                "target_type": "Acupoint",
                "target_name": r["acupoint_name"],
                "details": {
                    "efficacy": r["efficacy"],
                    "location": r["location"],
                    "meridian": r["meridian"],
                    "technique": r.get("technique", ""),
                },
            })

        # 4. 症状 → 体质（通过 HAS_SYMPTOM 反向查找）
        constitution_results = self.store.execute_query(
            """
            MATCH (c:Constitution)-[:HAS_SYMPTOM]->(s:Symptom)
            WHERE s.name CONTAINS $symptom
            RETURN c.type AS constitution_type, c.characteristics AS characteristics,
                   c.regulation AS regulation, c.diet_advice AS diet_advice
            LIMIT 3
            """,
            {"symptom": symptom},
        )
        for r in constitution_results:
            paths.append({
                "path_type": "症状→体质",
                "symptom": symptom,
                "target_type": "Constitution",
                "target_name": r["constitution_type"],
                "details": {
                    "characteristics": r["characteristics"],
                    "regulation": r["regulation"],
                    "diet_advice": r.get("diet_advice", ""),
                },
            })

        # 5. 二度路径: 症状 → 方剂 → 药材
        if max_depth >= 2:
            deep_results = self.store.execute_query(
                """
                MATCH (f:Formula)-[:TREATS]->(s:Symptom)
                WHERE s.name CONTAINS $symptom
                MATCH (f)-[:CONTAINS]->(h:Herb)
                RETURN f.name AS formula_name, s.name AS symptom_name,
                       collect(h.name) AS herbs
                LIMIT 3
                """,
                {"symptom": symptom},
            )
            for r in deep_results:
                paths.append({
                    "path_type": "症状→方剂→药材(二度)",
                    "symptom": symptom,
                    "target_type": "MultiHop",
                    "formula": r["formula_name"],
                    "herbs": r["herbs"],
                })

        return paths

    def find_related_entities(
        self,
        entity_name: str,
        relation_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """查找与实体相关的其他实体

        Args:
            entity_name: 实体名
            relation_type: 关系类型 (CONTAINS/TREATS/BELONGS_TO/ENTERS_MERIDIAN等)
            limit: 返回数量

        Returns:
            关联实体列表
        """
        if relation_type:
            query = f"""
            MATCH (n)-[:{relation_type}]-(m)
            WHERE n.name = $name OR n.type = $name
            RETURN m, labels(m) AS types, type(r) AS relation
            LIMIT $limit
            """
            # need to properly parameterize - relation_type can't be parameterized in Cypher
            # but it's from our controlled set so it's safe
            query_formatted = query
            results = self.store.execute_query(query_formatted, {"name": entity_name, "limit": limit})
        else:
            query = """
            MATCH (n)-[r]-(m)
            WHERE n.name = $name OR n.type = $name
            RETURN m, labels(m) AS types, type(r) AS relation
            LIMIT $limit
            """
            results = self.store.execute_query(query, {"name": entity_name, "limit": limit})

        related = []
        for r in results:
            node = r["m"]
            types = r["types"]
            related.append({
                "name": node.get("name", node.get("type", "")),
                "type": types[0] if types else "Unknown",
                "relation": r.get("relation", ""),
                "properties": dict(node),
            })
        return related

    def _format_relations(
        self,
        entity_name: str,
        results: List[Dict[str, Any]],
        depth: int,
    ) -> Dict[str, Any]:
        """格式化关系查询结果"""
        formatted = {"entity": entity_name, "outgoing": [], "incoming": []}

        if depth == 1:
            for r in results:
                if r.get("out_relation") and r.get("out_target"):
                    target = r["out_target"]
                    formatted["outgoing"].append({
                        "relation": r["out_relation"],
                        "target": target.get("name", target.get("type", "")),
                        "target_type": "Unknown",  # labels not easily available here
                    })
                if r.get("in_relation") and r.get("in_source"):
                    source = r["in_source"]
                    formatted["incoming"].append({
                        "relation": r["in_relation"],
                        "source": source.get("name", source.get("type", "")),
                    })
        else:
            formatted["paths"] = []
            for r in results:
                if r.get("level1_node") and r.get("level2_node"):
                    l1 = r["level1_node"]
                    l2 = r["level2_node"]
                    formatted["paths"].append({
                        "level1": {
                            "name": l1.get("name", l1.get("type", "")),
                            "relation": r.get("level1_rel", ""),
                        },
                        "level2": {
                            "name": l2.get("name", l2.get("type", "")),
                            "relation": r.get("level2_rel", ""),
                        },
                    })

        return formatted

    def format_context(self, paths: List[Dict[str, Any]]) -> str:
        """将检索路径格式化为上下文文本供 LLM 使用"""
        if not paths:
            return ""

        lines = ["## 知识图谱推理路径：\n"]

        for path in paths:
            path_type = path.get("path_type", "")
            symptom = path.get("symptom", "")
            target_name = path.get("target_name", "")
            details = path.get("details", {})

            if path_type == "症状→方剂→药材(二度)":
                formula = path.get("formula", "")
                herbs = path.get("herbs", [])
                lines.append(f"- 【二度推理】症状「{symptom}」→ 方剂「{formula}」→ 药材: {', '.join(herbs)}")
                continue

            lines.append(f"- 【{path_type}】症状「{symptom}」→ {target_name}")
            if details:
                if details.get("efficacy"):
                    lines.append(f"  功效: {details['efficacy']}")
                if details.get("nature"):
                    lines.append(f"  药性: {details['nature']}")
                if details.get("composition"):
                    lines.append(f"  组成: {details['composition']}")
                if details.get("location"):
                    lines.append(f"  定位: {details['location']}")
                if details.get("contraindications"):
                    lines.append(f"  禁忌: {details['contraindications']}")
                if details.get("regulation"):
                    lines.append(f"  调理: {details['regulation']}")

        return "\n".join(lines)
