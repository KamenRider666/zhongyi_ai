"""知识图谱构建器 - 从结构化数据构建中医知识图谱"""

import re
from typing import Any, Dict, List

from src.data.database import TCMDatabase
from src.graphrag.graph_store import Neo4jGraphStore


class TCMGraphBuilder:
    """中医知识图谱构建器"""

    def __init__(self, graph_store: Neo4jGraphStore, tcm_db: TCMDatabase):
        self.store = graph_store
        self.db = tcm_db

    def build_full_graph(self) -> None:
        """构建完整知识图谱"""
        print("🏗️ 开始构建中医知识图谱...")

        self.store.create_constraints()

        # 1. 创建实体节点
        self._create_formula_nodes()
        self._create_herb_nodes()
        self._create_acupoint_nodes()
        self._create_constitution_nodes()
        self._create_symptom_nodes()
        self._create_meridian_nodes()
        self._create_category_nodes()
        self._create_book_nodes()
        self._create_nature_nodes()

        # 2. 创建关系边
        self._create_formula_herb_relations()
        self._create_formula_symptom_relations()
        self._create_formula_category_relations()
        self._create_formula_book_relations()
        self._create_herb_meridian_relations()
        self._create_herb_symptom_relations()
        self._create_herb_nature_relations()
        self._create_acupoint_meridian_relations()
        self._create_acupoint_symptom_relations()
        self._create_constitution_symptom_relations()
        self._create_constitution_acupoint_relations()

        stats = self.store.get_stats()
        print(f"✓ 知识图谱构建完成: {stats['nodes']} 个节点, {stats['relationships']} 条关系")

    def _create_formula_nodes(self) -> None:
        """创建方剂节点"""
        formulas = self.db.search_fangji(limit=1000)
        for f in formulas:
            self.store.execute_write(
                """
                MERGE (f:Formula {name: $name})
                SET f.alias = $alias,
                    f.composition = $composition,
                    f.usage = $usage,
                    f.efficacy = $efficacy,
                    f.indications = $indications,
                    f.contraindications = $contraindications,
                    f.notes = $notes
                """,
                {
                    "name": f["name"],
                    "alias": f.get("alias", ""),
                    "composition": f["composition"],
                    "usage": f.get("usage_method", ""),
                    "efficacy": f["efficacy"],
                    "indications": f["indications"],
                    "contraindications": f.get("contraindications", ""),
                    "notes": f.get("notes", ""),
                },
            )

    def _create_herb_nodes(self) -> None:
        """创建药材节点"""
        herbs = self.db.search_herb(limit=1000)
        for h in herbs:
            self.store.execute_write(
                """
                MERGE (h:Herb {name: $name})
                SET h.latin_name = $latin_name,
                    h.alias = $alias,
                    h.nature = $nature,
                    h.taste = $taste,
                    h.efficacy = $efficacy,
                    h.indications = $indications,
                    h.dosage = $dosage,
                    h.toxicity = $toxicity,
                    h.contraindications = $contraindications
                """,
                {
                    "name": h["name"],
                    "latin_name": h.get("latin_name", ""),
                    "alias": h.get("alias", ""),
                    "nature": h["nature"],
                    "taste": h["taste"],
                    "efficacy": h["efficacy"],
                    "indications": h["indications"],
                    "dosage": h.get("dosage", ""),
                    "toxicity": h.get("toxicity", "无毒"),
                    "contraindications": h.get("contraindications", ""),
                },
            )

    def _create_acupoint_nodes(self) -> None:
        """创建穴位节点"""
        acupoints = self.db.search_acupoint(limit=1000)
        for a in acupoints:
            self.store.execute_write(
                """
                MERGE (a:Acupoint {name: $name})
                SET a.pinyin = $pinyin,
                    a.location = $location,
                    a.method = $method,
                    a.efficacy = $efficacy,
                    a.indications = $indications,
                    a.technique = $technique,
                    a.cautions = $cautions
                """,
                {
                    "name": a["name"],
                    "pinyin": a.get("pinyin", ""),
                    "location": a["location"],
                    "method": a.get("method", ""),
                    "efficacy": a["efficacy"],
                    "indications": a["indications"],
                    "technique": a.get("technique", ""),
                    "cautions": a.get("cautions", ""),
                },
            )

    def _create_constitution_nodes(self) -> None:
        """创建体质节点"""
        constitutions = self.db.list_constitutions()
        for c in constitutions:
            self.store.execute_write(
                """
                MERGE (c:Constitution {type: $type})
                SET c.characteristics = $characteristics,
                    c.tendency = $tendency,
                    c.regulation = $regulation,
                    c.diet_advice = $diet_advice,
                    c.exercise_advice = $exercise_advice
                """,
                {
                    "type": c["type_name"],
                    "characteristics": c["characteristics"],
                    "tendency": c.get("tendency", ""),
                    "regulation": c["regulation"],
                    "diet_advice": c.get("diet_advice", ""),
                    "exercise_advice": c.get("exercise_advice", ""),
                },
            )

    def _extract_symptoms(self, text: str) -> List[str]:
        """从文本中提取症状关键词"""
        # 常见中医症状关键词
        symptom_keywords = [
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
            "出血", "鼻衄", "齿衄", "便血", "尿血",
            "中风", "半身不遂", "口眼歪斜",
            "消渴", "消瘦", "肥胖", "消谷善饥",
            "遗精", "阳痿", "早泄", "不孕",
            "惊风", "癫狂", "痫证", "烦躁",
            "疮疡", "疔疮", "痈肿", "丹毒",
            "乳胀", "乳房胀痛", "胁痛", "两胁作痛",
        ]
        found = []
        for kw in symptom_keywords:
            if kw in text:
                found.append(kw)
        return found

    def _extract_herbs_from_composition(self, composition: str) -> List[str]:
        """从方剂组成文本中提取药材名"""
        # 去掉剂量和单位，只保留药材名
        # 格式如: "麻黄9g、桂枝6g、杏仁9g、炙甘草3g"
        parts = re.split(r"[、，,]", composition)
        herbs = []
        for part in parts:
            # 去掉剂量数字和单位
            name = re.sub(r"\d+[g克ml毫升片枚个只]", "", part).strip()
            # 去掉炮制前缀（炙、煨、炒等）保留核心名
            name = re.sub(r"^(炙|煨|炒|生|熟|制|酒|醋|盐|蜜|清|淡|鲜)", "", name).strip()
            if name:
                herbs.append(name)
        return herbs

    def _create_symptom_nodes(self) -> None:
        """创建症状节点（从方剂和药材的主治文本中提取）"""
        formulas = self.db.search_fangji(limit=1000)
        herbs = self.db.search_herb(limit=1000)
        acupoints = self.db.search_acupoint(limit=1000)

        all_symptoms = set()
        for f in formulas:
            all_symptoms.update(self._extract_symptoms(f["indications"]))
        for h in herbs:
            all_symptoms.update(self._extract_symptoms(h["indications"]))
        for a in acupoints:
            all_symptoms.update(self._extract_symptoms(a["indications"]))

        for s in all_symptoms:
            self.store.execute_write(
                "MERGE (s:Symptom {name: $name})",
                {"name": s},
            )

    def _create_meridian_nodes(self) -> None:
        """创建经络/归经节点"""
        meridians = [
            "肺", "大肠", "胃", "脾", "心", "小肠",
            "膀胱", "肾", "心包", "三焦", "胆", "肝",
            "任脉", "督脉",
            "足阳明胃经", "手阳明大肠经", "手厥阴心包经",
            "足太阴脾经", "足厥阴肝经", "足少阴肾经",
            "手少阳三焦经", "足少阳胆经", "足太阳膀胱经",
            "手太阴肺经", "手少阴心经", "手太阳小肠经",
        ]
        for m in meridians:
            self.store.execute_write(
                "MERGE (m:Meridian {name: $name})",
                {"name": m},
            )

    def _create_category_nodes(self) -> None:
        """创建方剂分类节点"""
        categories = ["解表剂", "补益剂", "和解剂", "祛痰剂", "祛湿剂", "清热剂", "温里剂"]
        for cat in categories:
            self.store.execute_write(
                "MERGE (cat:Category {name: $name})",
                {"name": cat},
            )

    def _create_book_nodes(self) -> None:
        """创建经典书籍节点"""
        books = [
            "《伤寒论》", "《金匮要略》", "《黄帝内经》",
            "《太平惠民和剂局方》", "《小儿药证直诀》",
            "《温病条辨》", "《千金方》", "《本草纲目》",
        ]
        for b in books:
            self.store.execute_write(
                "MERGE (b:Book {name: $name})",
                {"name": b},
            )

    def _create_nature_nodes(self) -> None:
        """创建药性节点"""
        natures = ["寒", "热", "温", "凉", "平", "大热", "微温"]
        for n in natures:
            self.store.execute_write(
                "MERGE (nat:Nature {name: $name})",
                {"name": n},
            )

    def _create_formula_herb_relations(self) -> None:
        """创建方剂-药材关系 (CONTAINS)"""
        formulas = self.db.search_fangji(limit=1000)
        for f in formulas:
            herbs = self._extract_herbs_from_composition(f["composition"])
            for herb in herbs:
                self.store.execute_write(
                    """
                    MATCH (f:Formula {name: $formula_name})
                    MERGE (h:Herb {name: $herb_name})
                    MERGE (f)-[r:CONTAINS]->(h)
                    SET r.role = '组成药材'
                    """,
                    {"formula_name": f["name"], "herb_name": herb},
                )

    def _create_formula_symptom_relations(self) -> None:
        """创建方剂-症状关系 (TREATS)"""
        formulas = self.db.search_fangji(limit=1000)
        for f in formulas:
            symptoms = self._extract_symptoms(f["indications"])
            for s in symptoms:
                self.store.execute_write(
                    """
                    MATCH (f:Formula {name: $formula_name})
                    MERGE (s:Symptom {name: $symptom_name})
                    MERGE (f)-[r:TREATS]->(s)
                    SET r.source = '主治'
                    """,
                    {"formula_name": f["name"], "symptom_name": s},
                )

    def _create_formula_category_relations(self) -> None:
        """创建方剂-分类关系 (BELONGS_TO)"""
        formulas = self.db.search_fangji(limit=1000)
        for f in formulas:
            self.store.execute_write(
                """
                MATCH (f:Formula {name: $formula_name})
                MERGE (cat:Category {name: $category_name})
                MERGE (f)-[r:BELONGS_TO]->(cat)
                """,
                {"formula_name": f["name"], "category_name": f["category"]},
            )

    def _create_formula_book_relations(self) -> None:
        """创建方剂-出处关系 (SOURCE_FROM)"""
        formulas = self.db.search_fangji(limit=1000)
        for f in formulas:
            self.store.execute_write(
                """
                MATCH (f:Formula {name: $formula_name})
                MERGE (b:Book {name: $book_name})
                MERGE (f)-[r:SOURCE_FROM]->(b)
                """,
                {"formula_name": f["name"], "book_name": f["source"]},
            )

    def _create_herb_meridian_relations(self) -> None:
        """创建药材-归经关系 (ENTERS_MERIDIAN)"""
        herbs = self.db.search_herb(limit=1000)
        for h in herbs:
            # 归经可能是 "肺、膀胱" 或 "脾、肺、心、肾"
            meridians = h["meridian"].replace("、", ",").replace("，", ",").split(",")
            for m in meridians:
                m = m.strip()
                if m:
                    self.store.execute_write(
                        """
                        MATCH (h:Herb {name: $herb_name})
                        MERGE (m:Meridian {name: $meridian_name})
                        MERGE (h)-[r:ENTERS_MERIDIAN]->(m)
                        """,
                        {"herb_name": h["name"], "meridian_name": m},
                    )

    def _create_herb_symptom_relations(self) -> None:
        """创建药材-症状关系 (TREATS)"""
        herbs = self.db.search_herb(limit=1000)
        for h in herbs:
            symptoms = self._extract_symptoms(h["indications"])
            for s in symptoms:
                self.store.execute_write(
                    """
                    MATCH (h:Herb {name: $herb_name})
                    MERGE (s:Symptom {name: $symptom_name})
                    MERGE (h)-[r:TREATS]->(s)
                    SET r.source = '主治'
                    """,
                    {"herb_name": h["name"], "symptom_name": s},
                )

    def _create_herb_nature_relations(self) -> None:
        """创建药材-药性关系 (HAS_NATURE)"""
        herbs = self.db.search_herb(limit=1000)
        for h in herbs:
            self.store.execute_write(
                """
                MATCH (h:Herb {name: $herb_name})
                MERGE (nat:Nature {name: $nature_name})
                MERGE (h)-[r:HAS_NATURE]->(nat)
                """,
                {"herb_name": h["name"], "nature_name": h["nature"]},
            )

    def _create_acupoint_meridian_relations(self) -> None:
        """创建穴位-经络关系 (BELONGS_TO)"""
        acupoints = self.db.search_acupoint(limit=1000)
        for a in acupoints:
            self.store.execute_write(
                """
                MATCH (a:Acupoint {name: $acupoint_name})
                MERGE (m:Meridian {name: $meridian_name})
                MERGE (a)-[r:BELONGS_TO]->(m)
                """,
                {"acupoint_name": a["name"], "meridian_name": a["meridian"]},
            )

    def _create_acupoint_symptom_relations(self) -> None:
        """创建穴位-症状关系 (TREATS)"""
        acupoints = self.db.search_acupoint(limit=1000)
        for a in acupoints:
            symptoms = self._extract_symptoms(a["indications"])
            for s in symptoms:
                self.store.execute_write(
                    """
                    MATCH (a:Acupoint {name: $acupoint_name})
                    MERGE (s:Symptom {name: $symptom_name})
                    MERGE (a)-[r:TREATS]->(s)
                    SET r.source = '主治'
                    """,
                    {"acupoint_name": a["name"], "symptom_name": s},
                )

    def _create_constitution_symptom_relations(self) -> None:
        """创建体质-症状关系 (MATCHES)"""
        constitutions = self.db.list_constitutions()
        for c in constitutions:
            symptoms = self._extract_symptoms(c["characteristics"])
            for s in symptoms:
                self.store.execute_write(
                    """
                    MATCH (c:Constitution {type: $constitution_type})
                    MERGE (s:Symptom {name: $symptom_name})
                    MERGE (c)-[r:HAS_SYMPTOM]->(s)
                    """,
                    {"constitution_type": c["type_name"], "symptom_name": s},
                )

    def _create_constitution_acupoint_relations(self) -> None:
        """创建体质-穴位推荐关系"""
        constitutions = self.db.list_constitutions()
        for c in constitutions:
            advice = c.get("acupoint_advice", "")
            if advice:
                # 提取穴位名（中文常见穴位）
                acupoint_names = re.findall(
                    r"足三里|合谷|内关|三阴交|太冲|关元|百会|风池|涌泉|气海|命门|丰隆|阴陵泉|太溪",
                    advice,
                )
                for name in acupoint_names:
                    self.store.execute_write(
                        """
                        MATCH (c:Constitution {type: $constitution_type})
                        MERGE (a:Acupoint {name: $acupoint_name})
                        MERGE (c)-[r:RECOMMENDS_ACUPOINT]->(a)
                        SET r.source = '调理建议'
                        """,
                        {"constitution_type": c["type_name"], "acupoint_name": name},
                    )
