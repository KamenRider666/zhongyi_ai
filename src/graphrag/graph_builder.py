"""知识图谱构建器 - 从 MySQL 新表结构构建中医知识图谱

适配 seedmysql.py 导入的 4 张表:
  - formulas  (方剂/中成药)
  - herbs     (药材)
  - diseases  (疾病 - 层级树)
  - syndromes (证候 - 层级树)
"""

import json
import re
from typing import Any, Dict, List, Tuple

import pymysql

from src.config import settings
from src.graphrag.graph_store import Neo4jGraphStore


class TCMGraphBuilder:
    """中医知识图谱构建器"""

    def __init__(self, graph_store: Neo4jGraphStore):
        self.store = graph_store
        self._conn = pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )

    def _query(self, sql: str, *args) -> List[Dict[str, Any]]:
        """执行查询，返回 dict 列表"""
        with self._conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()

    # ═══════════════════════════════════════
    #  build
    # ═══════════════════════════════════════

    def build_full_graph(self) -> None:
        print("开始构建中医知识图谱...")

        self.store.create_constraints()

        # 1. 节点
        self._create_formula_nodes()
        self._create_herb_nodes()
        self._create_disease_nodes()
        self._create_syndrome_nodes()
        self._create_symptom_nodes()
        self._create_meridian_nodes()
        self._create_category_nodes()

        # 2. 关系
        self._create_formula_category_relations()
        self._create_formula_symptom_relations()
        self._create_herb_meridian_relations()
        self._create_herb_symptom_relations()
        self._create_herb_nature_relations()
        self._create_disease_hierarchy()
        self._create_syndrome_hierarchy()
        self._create_disease_symptom_relations()
        self._create_syndrome_symptom_relations()
        self._create_formula_disease_relations()

        stats = self.store.get_stats()
        print(f"知识图谱构建完成: {stats['nodes']} 节点, {stats['relationships']} 关系")

    # ═══════════════════════════════════════
    #  节点创建
    # ═══════════════════════════════════════

    def _create_formula_nodes(self) -> None:
        rows = self._query("SELECT * FROM formulas")
        for r in rows:
            self.store.execute_write(
                """
                MERGE (f:Formula {name: $name})
                SET f.pinyin = $pinyin,
                    f.ingredients = $ingredients,
                    f.functions = $functions,
                    f.analysis = $analysis,
                    f.clinical_use = $clinical_use,
                    f.contraindications = $contraindications,
                    f.usage = $usage
                """,
                {
                    "name": r["name"],
                    "pinyin": r.get("pinyin", ""),
                    "ingredients": r.get("ingredients", ""),
                    "functions": r.get("functions", ""),
                    "analysis": r.get("analysis", ""),
                    "clinical_use": r.get("clinical_use", ""),
                    "contraindications": r.get("contraindications", ""),
                    "usage": r.get("usage", ""),
                },
            )
        print(f"  ✓ Formula 节点: {len(rows)}")

    def _create_herb_nodes(self) -> None:
        rows = self._query("SELECT * FROM herbs")
        for r in rows:
            nature, taste, meridian = self._parse_nature_taste_meridian(
                r.get("nature_taste_meridian", "")
            )
            self.store.execute_write(
                """
                MERGE (h:Herb {name: $name})
                SET h.pinyin = $pinyin,
                    h.latin_name = $latin_name,
                    h.nature = $nature,
                    h.taste = $taste,
                    h.efficacy = $efficacy,
                    h.dosage = $dosage,
                    h.caution = $caution
                """,
                {
                    "name": r["name"],
                    "pinyin": r.get("pinyin", ""),
                    "latin_name": r.get("latin_name", ""),
                    "nature": nature,
                    "taste": taste,
                    "efficacy": r.get("functions", ""),
                    "dosage": r.get("usage", ""),
                    "caution": r.get("caution", ""),
                },
            )
            # 归经单独存为关系
            if meridian:
                for m in self._split_meridians(meridian):
                    if m:
                        self.store.execute_write(
                            """
                            MATCH (h:Herb {name: $name})
                            MERGE (m:Meridian {name: $meridian})
                            MERGE (h)-[r:ENTERS_MERIDIAN]->(m)
                            """,
                            {"name": r["name"], "meridian": m},
                        )
        print(f"  ✓ Herb 节点: {len(rows)}")

    def _create_disease_nodes(self) -> None:
        rows = self._query("SELECT * FROM diseases")
        for r in rows:
            aliases = r.get("aliases")
            if isinstance(aliases, str):
                try:
                    aliases = json.loads(aliases)
                except json.JSONDecodeError:
                    aliases = []
            alias_str = "、".join(aliases) if isinstance(aliases, list) else ""
            self.store.execute_write(
                """
                MERGE (d:Disease {code: $code})
                SET d.name = $name,
                    d.aliases = $aliases,
                    d.definition = $definition,
                    d.is_category = $is_category
                """,
                {
                    "code": r["code"],
                    "name": r["name"],
                    "aliases": alias_str,
                    "definition": r.get("definition", ""),
                    "is_category": bool(r.get("is_category")),
                },
            )
        print(f"  ✓ Disease 节点: {len(rows)}")

    def _create_syndrome_nodes(self) -> None:
        rows = self._query("SELECT * FROM syndromes")
        for r in rows:
            aliases = r.get("aliases")
            if isinstance(aliases, str):
                try:
                    aliases = json.loads(aliases)
                except json.JSONDecodeError:
                    aliases = []
            alias_str = "、".join(aliases) if isinstance(aliases, list) else ""
            self.store.execute_write(
                """
                MERGE (s:Syndrome {code: $code})
                SET s.name = $name,
                    s.aliases = $aliases,
                    s.definition = $definition,
                    s.is_category = $is_category
                """,
                {
                    "code": r["code"],
                    "name": r["name"],
                    "aliases": alias_str,
                    "definition": r.get("definition", ""),
                    "is_category": bool(r.get("is_category")),
                },
            )
        print(f"  ✓ Syndrome 节点: {len(rows)}")

    def _create_symptom_nodes(self) -> None:
        symptoms = set()
        # 从 formulas.clinical_use 提取
        formulas = self._query("SELECT clinical_use FROM formulas")
        for f in formulas:
            symptoms.update(self._extract_symptoms(f.get("clinical_use", "")))
        # 从 herbs.functions 提取
        herbs = self._query("SELECT functions FROM herbs")
        for h in herbs:
            symptoms.update(self._extract_symptoms(h.get("functions", "")))
        # 从 diseases.definition 提取
        diseases = self._query("SELECT definition FROM diseases")
        for d in diseases:
            symptoms.update(self._extract_symptoms(d.get("definition", "")))
        # 从 syndromes.definition 提取
        syndromes = self._query("SELECT definition FROM syndromes")
        for s in syndromes:
            symptoms.update(self._extract_symptoms(s.get("definition", "")))

        for sym in symptoms:
            self.store.execute_write(
                "MERGE (s:Symptom {name: $name})",
                {"name": sym},
            )
        print(f"  ✓ Symptom 节点: {len(symptoms)}")

    def _create_meridian_nodes(self) -> None:
        meridians = [
            "肺", "大肠", "胃", "脾", "心", "小肠",
            "膀胱", "肾", "心包", "三焦", "胆", "肝",
        ]
        for m in meridians:
            self.store.execute_write("MERGE (m:Meridian {name: $name})", {"name": m})
        print(f"  ✓ Meridian 节点: {len(meridians)}")

    def _create_category_nodes(self) -> None:
        # 从 formulas 表收集所有分类
        rows = self._query("SELECT DISTINCT category FROM formulas WHERE category IS NOT NULL")
        for r in rows:
            cat = r["category"].strip()
            if cat:
                self.store.execute_write(
                    "MERGE (cat:Category {name: $name})",
                    {"name": cat},
                )
        print(f"  ✓ Category 节点: {len(rows)}")

    # ═══════════════════════════════════════
    #  关系创建
    # ═══════════════════════════════════════

    def _create_formula_category_relations(self) -> None:
        rows = self._query("SELECT name, category FROM formulas WHERE category IS NOT NULL")
        count = 0
        for r in rows:
            self.store.execute_write(
                """
                MATCH (f:Formula {name: $name})
                MERGE (cat:Category {name: $category})
                MERGE (f)-[rel:BELONGS_TO]->(cat)
                """,
                {"name": r["name"], "category": r["category"].strip()},
            )
            count += 1
        print(f"  ✓ Formula → Category: {count}")

    def _create_formula_symptom_relations(self) -> None:
        rows = self._query("SELECT name, clinical_use FROM formulas")
        count = 0
        for r in rows:
            symptoms = self._extract_symptoms(r.get("clinical_use", ""))
            for s in symptoms:
                self.store.execute_write(
                    """
                    MATCH (f:Formula {name: $name})
                    MERGE (s:Symptom {name: $symptom})
                    MERGE (f)-[rel:TREATS]->(s)
                    """,
                    {"name": r["name"], "symptom": s},
                )
                count += 1
        print(f"  ✓ Formula → Symptom: {count}")

    def _create_herb_meridian_relations(self) -> None:
        """已在 _create_herb_nodes 中处理，此处跳过"""
        pass

    def _create_herb_symptom_relations(self) -> None:
        rows = self._query("SELECT name, functions FROM herbs")
        count = 0
        for r in rows:
            symptoms = self._extract_symptoms(r.get("functions", ""))
            for s in symptoms:
                self.store.execute_write(
                    """
                    MATCH (h:Herb {name: $name})
                    MERGE (s:Symptom {name: $symptom})
                    MERGE (h)-[rel:TREATS]->(s)
                    """,
                    {"name": r["name"], "symptom": s},
                )
                count += 1
        print(f"  ✓ Herb → Symptom: {count}")

    def _create_herb_nature_relations(self) -> None:
        rows = self._query("SELECT name, nature_taste_meridian FROM herbs")
        count = 0
        for r in rows:
            nature, _, _ = self._parse_nature_taste_meridian(
                r.get("nature_taste_meridian", "")
            )
            if nature:
                for n in self._split_nature(nature):
                    if n:
                        self.store.execute_write(
                            """
                            MATCH (h:Herb {name: $name})
                            MERGE (nat:Nature {name: $nature})
                            MERGE (h)-[rel:HAS_NATURE]->(nat)
                            """,
                            {"name": r["name"], "nature": n},
                        )
                        count += 1
        print(f"  ✓ Herb → Nature: {count}")

    def _create_disease_hierarchy(self) -> None:
        """根据 parent_code 建立 Disease 的层级关系"""
        rows = self._query(
            "SELECT code, parent_code, name FROM diseases WHERE parent_code IS NOT NULL"
        )
        count = 0
        for r in rows:
            self.store.execute_write(
                """
                MATCH (child:Disease {code: $code})
                MATCH (parent:Disease {code: $parent_code})
                MERGE (child)-[rel:SUBCATEGORY_OF]->(parent)
                """,
                {"code": r["code"], "parent_code": r["parent_code"]},
            )
            count += 1
        print(f"  ✓ Disease 层级: {count}")

    def _create_syndrome_hierarchy(self) -> None:
        rows = self._query(
            "SELECT code, parent_code, name FROM syndromes WHERE parent_code IS NOT NULL"
        )
        count = 0
        for r in rows:
            self.store.execute_write(
                """
                MATCH (child:Syndrome {code: $code})
                MATCH (parent:Syndrome {code: $parent_code})
                MERGE (child)-[rel:SUBCATEGORY_OF]->(parent)
                """,
                {"code": r["code"], "parent_code": r["parent_code"]},
            )
            count += 1
        print(f"  ✓ Syndrome 层级: {count}")

    def _create_disease_symptom_relations(self) -> None:
        rows = self._query("SELECT code, definition FROM diseases")
        count = 0
        for r in rows:
            symptoms = self._extract_symptoms(r.get("definition", ""))
            for s in symptoms:
                self.store.execute_write(
                    """
                    MATCH (d:Disease {code: $code})
                    MERGE (s:Symptom {name: $symptom})
                    MERGE (d)-[rel:HAS_SYMPTOM]->(s)
                    """,
                    {"code": r["code"], "symptom": s},
                )
                count += 1
        print(f"  ✓ Disease → Symptom: {count}")

    def _create_syndrome_symptom_relations(self) -> None:
        rows = self._query("SELECT code, definition FROM syndromes")
        count = 0
        for r in rows:
            symptoms = self._extract_symptoms(r.get("definition", ""))
            for s in symptoms:
                self.store.execute_write(
                    """
                    MATCH (s:Syndrome {code: $code})
                    MERGE (sym:Symptom {name: $symptom})
                    MERGE (s)-[rel:HAS_SYMPTOM]->(sym)
                    """,
                    {"code": r["code"], "symptom": s},
                )
                count += 1
        print(f"  ✓ Syndrome → Symptom: {count}")

    def _create_formula_disease_relations(self) -> None:
        """从 clinical_use 中匹配疾病名"""
        rows = self._query("SELECT name, clinical_use FROM formulas")
        diseases = self._query("SELECT code, name FROM diseases")
        disease_names = {d["name"] for d in diseases}
        count = 0
        for r in rows:
            clinical = r.get("clinical_use", "")
            for dn in disease_names:
                if len(dn) >= 2 and dn in clinical:
                    self.store.execute_write(
                        """
                        MATCH (f:Formula {name: $formula})
                        MATCH (d:Disease {name: $disease})
                        MERGE (f)-[rel:TREATS]->(d)
                        """,
                        {"formula": r["name"], "disease": dn},
                    )
                    count += 1
        print(f"  ✓ Formula → Disease: {count}")

    # ═══════════════════════════════════════
    #  解析工具
    # ═══════════════════════════════════════

    def _parse_nature_taste_meridian(self, text: str) -> Tuple[str, str, str]:
        """解析 "辛、苦，凉。归肺、肝经。" → (nature, taste, meridian)"""
        nature = ""
        taste = ""
        meridian = ""
        if not text:
            return nature, taste, meridian
        # 按句号拆
        parts = text.replace("。", "：").split("：")
        if len(parts) >= 1:
            nature_taste = parts[0].strip()
            # 尝试拆四气五味
            if "，" in nature_taste or "、" in nature_taste:
                items = re.split(r"[，,、]", nature_taste)
                # 四气通常在后面
                four_qi = {"寒", "热", "温", "凉", "平", "大热", "微温", "微寒", "大寒"}
                tastes = []
                natures = []
                for item in items:
                    item = item.strip()
                    if item in four_qi or item.endswith("寒") or item.endswith("热") or item.endswith("温") or item.endswith("凉"):
                        natures.append(item)
                    else:
                        tastes.append(item)
                nature = "、".join(natures) if natures else items[-1].strip() if items else ""
                taste = "、".join(tastes) if tastes else nature_taste
            else:
                taste = nature_taste

        if len(parts) >= 2:
            meridian = parts[1].strip()
            meridian = meridian.replace("归", "").replace("经", "").strip()

        return nature, taste, meridian

    def _split_meridians(self, text: str) -> List[str]:
        """拆分归经字符串，如 "肺、肝" → ["肺", "肝"]"""
        items = re.split(r"[，,、]", text)
        return [i.strip() for i in items if i.strip()]

    def _split_nature(self, text: str) -> List[str]:
        """拆分药性，如 "寒、凉" → ["寒", "凉"]"""
        items = re.split(r"[，,、]", text)
        return [i.strip() for i in items if i.strip()]

    def _extract_symptoms(self, text: str) -> List[str]:
        """从文本中提取症状关键词"""
        keywords = [
            "头痛", "发热", "恶寒", "咳嗽", "喘", "气喘", "胸闷",
            "腹痛", "腹泻", "便秘", "呕吐", "恶心", "食欲不振",
            "失眠", "多梦", "心悸", "眩晕", "头晕", "耳鸣",
            "腰痛", "腰膝酸软", "关节痛", "痹痛", "水肿", "浮肿",
            "汗出", "无汗", "自汗", "盗汗", "口渴", "口干",
            "口苦", "咽干", "目眩", "目赤", "鼻塞", "鼻衄",
            "面赤", "面色萎黄", "面色无华", "面色苍白",
            "乏力", "疲乏", "气短", "懒言", "语声低微",
            "手足心热", "手足不温", "畏寒", "怕冷",
            "月经不调", "经闭", "痛经", "带下",
            "痰多", "痰饮", "咳痰", "痰白", "痰黄",
            "出血", "便血", "尿血",
            "中风", "半身不遂", "口眼歪斜",
            "消渴", "消瘦", "肥胖", "消谷善饥",
            "遗精", "阳痿", "早泄", "不孕",
            "惊风", "癫狂", "痫证", "烦躁",
            "疮疡", "疔疮", "痈肿", "丹毒",
            "乳胀", "乳房胀痛", "胁痛", "两胁作痛",
            "抽搐", "神昏", "谵语", "意识模糊",
            "纳呆", "纳差", "腹胀", "嗳气", "吞酸",
            "小便不利", "尿少", "尿频", "尿痛",
            "鼻塞", "流涕", "喷嚏", "喉痒",
            "骨节痛", "四肢痛", "身痛", "项强",
            "面色无华", "面色晦暗", "唇甲色淡",
            "皮肤瘙痒", "皮疹", "湿疹",
            "吐血", "咯血",
            "五心烦热", "潮热", "盗汗",
            "目睛干涩", "视物模糊",
            "经行腹痛", "月经不调",
            "舌淡", "舌红", "苔白", "苔黄", "脉浮", "脉紧", "脉弦", "脉细",
        ]
        found = set()
        for kw in keywords:
            if kw in text:
                found.add(kw)
        return list(found)

    def close(self) -> None:
        self._conn.close()
