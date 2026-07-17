"""知识图谱构建器 - 从 MySQL 统一构建中医知识图谱（批量优化版）

数据源：MySQL agenttest 库（14 张表）
所有 Neo4j 写操作使用 UNWIND 批量写入，1000 条/批。

构建策略:
  1. 先建国标节点（diseases/syndromes/herbs/formulas）
  2. 再从诊疗词典丰富（按 name MERGE）
  3. 症状节点从 sym_dictionary 建（替代正则抽取）
  4. Disease→Symptom 优先用 ch_diag_comparison，正则兜底
  5. 诊疗词典表不存在时自动回退到纯正则模式
"""

import json
import re
from typing import Any, Dict, List, Tuple

import pymysql

from src.config import settings
from src.graphrag.graph_store import Neo4jGraphStore

BATCH_SIZE = 1000


class TCMGraphBuilder:
    """中医知识图谱构建器（批量优化版）"""

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
        self._has_diag_tables = self._check_diag_tables()
        self._symptom_names: list[str] | None = None  # 懒加载症状名集合

    def _query(self, sql: str, *args) -> List[Dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()

    def _check_diag_tables(self) -> bool:
        try:
            self._query("SELECT 1 FROM dictionary_diag_dic_sym_dictionary LIMIT 1")
            return True
        except Exception:
            print("  [INFO] 诊疗词典表不存在，将使用纯正则模式")
            return False

    def _batch_write(self, query: str, items: list[dict], label: str = "") -> int:
        """批量 UNWIND 写入，每 BATCH_SIZE 条一批"""
        total = len(items)
        if total == 0:
            print(f"  ✓ {label}: 0")
            return 0
        written = 0
        for i in range(0, total, BATCH_SIZE):
            batch = items[i:i + BATCH_SIZE]
            self.store.execute_write(query, {"batch": batch})
            written += len(batch)
            if total > BATCH_SIZE:
                print(f"\r    ...{written}/{total}", end="", flush=True)
        if total > BATCH_SIZE:
            print()
        print(f"  ✓ {label}: {total}")
        return total

    # ═══════════════════════════════════════
    #  主入口
    # ═══════════════════════════════════════

    def build_full_graph(self) -> None:
        print("=" * 60)
        print("构建中医知识图谱（批量优化版）")
        print(f"  诊疗词典: {'已启用' if self._has_diag_tables else '未启用（正则模式）'}")
        print(f"  批量大小: {BATCH_SIZE}")
        print("=" * 60)

        self.store.create_constraints()

        print("\n[1/3] 创建节点...")
        self._create_formula_nodes()
        self._create_herb_nodes()
        self._create_disease_nodes()
        self._create_syndrome_nodes()
        self._create_symptom_nodes()
        self._create_meridian_nodes()
        self._create_category_nodes()

        if self._has_diag_tables:
            self._enrich_disease_from_diag()
            self._enrich_syndrome_from_diag()
            self._create_therapy_nodes()

        print("\n[2/3] 创建关系...")
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

        if self._has_diag_tables:
            self._create_symptom_comparison_relations()

        print("\n[3/3] 统计...")
        stats = self.store.get_stats()
        print(f"\n知识图谱构建完成: {stats['nodes']} 节点, {stats['relationships']} 关系")

    # ═══════════════════════════════════════
    #  节点创建 — 批量 UNWIND
    # ═══════════════════════════════════════

    def _create_formula_nodes(self) -> None:
        rows = self._query("SELECT * FROM formulas")
        items = [{
            "name": r["name"], "pinyin": r.get("pinyin", ""),
            "ingredients": r.get("ingredients", ""), "functions": r.get("functions", ""),
            "analysis": r.get("analysis", ""), "clinical_use": r.get("clinical_use", ""),
            "contraindications": r.get("contraindications", ""), "usage": r.get("usage", ""),
        } for r in rows]
        self._batch_write("""
            UNWIND $batch AS row
            MERGE (f:Formula {name: row.name})
            SET f.pinyin = row.pinyin, f.ingredients = row.ingredients,
                f.functions = row.functions, f.analysis = row.analysis,
                f.clinical_use = row.clinical_use,
                f.contraindications = row.contraindications, f.usage = row.usage
        """, items, "Formula 节点")

    def _create_herb_nodes(self) -> None:
        rows = self._query("SELECT * FROM herbs")
        items = []
        meridian_pairs = []  # (herb_name, meridian) 收集后批量建关系
        for r in rows:
            nature, taste, meridian = self._parse_nature_taste_meridian(r.get("nature_taste_meridian", ""))
            items.append({
                "name": r["name"], "pinyin": r.get("pinyin", ""),
                "latin_name": r.get("latin_name", ""), "nature": nature, "taste": taste,
                "efficacy": r.get("functions", ""), "dosage": r.get("usage", ""),
                "caution": r.get("caution", ""),
            })
            if meridian:
                for m in self._split_meridians(meridian):
                    if m:
                        meridian_pairs.append({"herb": r["name"], "meridian": m})
        self._batch_write("""
            UNWIND $batch AS row
            MERGE (h:Herb {name: row.name})
            SET h.pinyin = row.pinyin, h.latin_name = row.latin_name,
                h.nature = row.nature, h.taste = row.taste,
                h.efficacy = row.efficacy, h.dosage = row.dosage, h.caution = row.caution
        """, items, "Herb 节点")
        # 批量建归经关系
        self._batch_write("""
            UNWIND $batch AS row
            MATCH (h:Herb {name: row.herb})
            MERGE (m:Meridian {name: row.meridian})
            MERGE (h)-[:ENTERS_MERIDIAN]->(m)
        """, meridian_pairs, "Herb → Meridian")

    def _create_disease_nodes(self) -> None:
        rows = self._query("SELECT * FROM diseases")
        items = []
        for r in rows:
            aliases = r.get("aliases")
            if isinstance(aliases, str):
                try:
                    aliases = json.loads(aliases)
                except json.JSONDecodeError:
                    aliases = []
            items.append({
                "code": r["code"], "name": r["name"],
                "aliases": "、".join(aliases) if isinstance(aliases, list) else "",
                "definition": r.get("definition", ""),
                "is_category": bool(r.get("is_category")),
            })
        self._batch_write("""
            UNWIND $batch AS row
            MERGE (d:Disease {code: row.code})
            SET d.name = row.name, d.aliases = row.aliases,
                d.definition = row.definition, d.is_category = row.is_category
        """, items, "Disease 节点")

    def _create_syndrome_nodes(self) -> None:
        rows = self._query("SELECT * FROM syndromes")
        items = []
        for r in rows:
            aliases = r.get("aliases")
            if isinstance(aliases, str):
                try:
                    aliases = json.loads(aliases)
                except json.JSONDecodeError:
                    aliases = []
            items.append({
                "code": r["code"], "name": r["name"],
                "aliases": "、".join(aliases) if isinstance(aliases, list) else "",
                "definition": r.get("definition", ""),
                "is_category": bool(r.get("is_category")),
            })
        self._batch_write("""
            UNWIND $batch AS row
            MERGE (s:Syndrome {code: row.code})
            SET s.name = row.name, s.aliases = row.aliases,
                s.definition = row.definition, s.is_category = row.is_category
        """, items, "Syndrome 节点")

    def _create_symptom_nodes(self) -> None:
        if self._has_diag_tables:
            rows = self._query("""
                SELECT id, code1, name, common_sign, main_sign,
                       dic_describe, directivity, pinyin_code
                FROM dictionary_diag_dic_sym_dictionary
                WHERE name IS NOT NULL AND name != ''
            """)
            items = [{
                "name": r["name"], "id": r["id"],
                "code": r.get("code1") or "",
                "common_sign": r.get("common_sign") or "0",
                "main_sign": r.get("main_sign") or "0",
                "describe": r.get("dic_describe") or "",
                "directivity": r.get("directivity") or "",
                "pinyin": r.get("pinyin_code") or "",
            } for r in rows]
            self._batch_write("""
                UNWIND $batch AS row
                MERGE (s:Symptom {name: row.name})
                SET s.diag_id = row.id,
                    s.code = COALESCE(s.code, row.code),
                    s.common_sign = row.common_sign,
                    s.main_sign = COALESCE(s.main_sign, row.main_sign),
                    s.description = COALESCE(s.description, row.describe),
                    s.directivity = COALESCE(s.directivity, row.directivity),
                    s.pinyin_code = COALESCE(s.pinyin_code, row.pinyin)
            """, items, "Symptom 节点 (诊疗词典)")
        else:
            symptoms = set()
            for table, col in [("formulas", "clinical_use"), ("herbs", "functions"),
                               ("diseases", "definition"), ("syndromes", "definition")]:
                rows = self._query(f"SELECT {col} FROM {table}")
                for r in rows:
                    symptoms.update(self._extract_symptoms(r.get(col, "")))
            items = [{"name": s} for s in symptoms]
            self._batch_write("""
                UNWIND $batch AS row
                MERGE (s:Symptom {name: row.name})
            """, items, "Symptom 节点 (正则抽取)")

    def _create_meridian_nodes(self) -> None:
        meridians = ["肺", "大肠", "胃", "脾", "心", "小肠",
                     "膀胱", "肾", "心包", "三焦", "胆", "肝"]
        items = [{"name": m} for m in meridians]
        self._batch_write("UNWIND $batch AS row MERGE (m:Meridian {name: row.name})",
                          items, "Meridian 节点")

    def _create_category_nodes(self) -> None:
        rows = self._query("SELECT DISTINCT category FROM formulas WHERE category IS NOT NULL AND category != ''")
        items = [{"name": r["category"].strip()} for r in rows if r["category"].strip()]
        self._batch_write("UNWIND $batch AS row MERGE (cat:Category {name: row.name})",
                          items, "Category 节点")

    # ═══════════════════════════════════════
    #  节点丰富 — 诊疗词典
    # ═══════════════════════════════════════

    def _enrich_disease_from_diag(self) -> None:
        rows = self._query("""
            SELECT id, code, name, common_sign, dic_describe, directivity, pinyin_code
            FROM dictionary_diag_dic_ch_diag_dictionary
            WHERE name IS NOT NULL AND name != ''
        """)
        items = [{
            "name": r["name"], "id": r["id"],
            "common_sign": r.get("common_sign") or "0",
            "directivity": r.get("directivity") or "",
            "pinyin": r.get("pinyin_code") or "",
            "describe": r.get("dic_describe") or "",
        } for r in rows]
        self._batch_write("""
            UNWIND $batch AS row
            MERGE (d:Disease {name: row.name})
            SET d.diag_id = row.id, d.common_sign = row.common_sign,
                d.directivity = COALESCE(d.directivity, row.directivity),
                d.pinyin_code = COALESCE(d.pinyin_code, row.pinyin),
                d.description = COALESCE(d.description, row.describe)
        """, items, "Disease 丰富 (诊疗词典)")

    def _enrich_syndrome_from_diag(self) -> None:
        rows = self._query("""
            SELECT id, code, name, common_sign, dic_describe, directivity, pinyin_code
            FROM dictionary_diag_dic_ch_yndrome_dictionary
            WHERE name IS NOT NULL AND name != ''
        """)
        items = [{
            "name": r["name"], "id": r["id"],
            "common_sign": r.get("common_sign") or "0",
            "directivity": r.get("directivity") or "",
            "pinyin": r.get("pinyin_code") or "",
            "describe": r.get("dic_describe") or "",
        } for r in rows]
        self._batch_write("""
            UNWIND $batch AS row
            MERGE (s:Syndrome {name: row.name})
            SET s.diag_id = row.id, s.common_sign = row.common_sign,
                s.directivity = COALESCE(s.directivity, row.directivity),
                s.pinyin_code = COALESCE(s.pinyin_code, row.pinyin),
                s.description = COALESCE(s.description, row.describe)
        """, items, "Syndrome 丰富 (诊疗词典)")

    def _create_therapy_nodes(self) -> None:
        rows = self._query("""
            SELECT id, code, name, dic_describe, directivity, pinyin_code
            FROM dictionary_diag_dic_ch_therapy_dictionary
            WHERE name IS NOT NULL AND name != ''
        """)
        items = [{
            "name": r["name"], "id": r["id"], "code": r.get("code") or "",
            "describe": r.get("dic_describe") or "",
            "directivity": r.get("directivity") or "",
            "pinyin": r.get("pinyin_code") or "",
        } for r in rows]
        self._batch_write("""
            UNWIND $batch AS row
            MERGE (t:Therapy {name: row.name})
            SET t.diag_id = row.id, t.code = row.code,
                t.description = row.describe, t.directivity = row.directivity,
                t.pinyin_code = row.pinyin
        """, items, "Therapy 节点")

    # ═══════════════════════════════════════
    #  关系创建 — 批量 UNWIND
    # ═══════════════════════════════════════

    def _create_formula_category_relations(self) -> None:
        rows = self._query("SELECT name, category FROM formulas WHERE category IS NOT NULL AND category != ''")
        items = [{"formula": r["name"], "category": r["category"].strip()} for r in rows]
        self._batch_write("""
            UNWIND $batch AS row
            MATCH (f:Formula {name: row.formula})
            MERGE (cat:Category {name: row.category})
            MERGE (f)-[:BELONGS_TO]->(cat)
        """, items, "Formula → Category")

    def _create_formula_symptom_relations(self) -> None:
        rows = self._query("SELECT name, clinical_use FROM formulas")
        pairs = []
        for r in rows:
            for s in self._extract_symptoms(r.get("clinical_use", "")):
                pairs.append({"formula": r["name"], "symptom": s})
        self._batch_write("""
            UNWIND $batch AS row
            MATCH (f:Formula {name: row.formula})
            MERGE (s:Symptom {name: row.symptom})
            MERGE (f)-[:TREATS]->(s)
        """, pairs, "Formula → Symptom")

    def _create_herb_meridian_relations(self) -> None:
        pass  # 已在 _create_herb_nodes 中批量处理

    def _create_herb_symptom_relations(self) -> None:
        rows = self._query("SELECT name, functions FROM herbs")
        pairs = []
        for r in rows:
            for s in self._extract_symptoms(r.get("functions", "")):
                pairs.append({"herb": r["name"], "symptom": s})
        self._batch_write("""
            UNWIND $batch AS row
            MATCH (h:Herb {name: row.herb})
            MERGE (s:Symptom {name: row.symptom})
            MERGE (h)-[:TREATS]->(s)
        """, pairs, "Herb → Symptom")

    def _create_herb_nature_relations(self) -> None:
        rows = self._query("SELECT name, nature_taste_meridian FROM herbs")
        pairs = []
        for r in rows:
            nature, _, _ = self._parse_nature_taste_meridian(r.get("nature_taste_meridian", ""))
            if nature:
                for n in self._split_nature(nature):
                    if n:
                        pairs.append({"herb": r["name"], "nature": n})
        self._batch_write("""
            UNWIND $batch AS row
            MATCH (h:Herb {name: row.herb})
            MERGE (nat:Nature {name: row.nature})
            MERGE (h)-[:HAS_NATURE]->(nat)
        """, pairs, "Herb → Nature")

    def _create_disease_hierarchy(self) -> None:
        rows = self._query("SELECT code, parent_code FROM diseases WHERE parent_code IS NOT NULL")
        items = [{"code": r["code"], "parent": r["parent_code"]} for r in rows]
        self._batch_write("""
            UNWIND $batch AS row
            MATCH (child:Disease {code: row.code})
            MATCH (parent:Disease {code: row.parent})
            MERGE (child)-[:SUBCATEGORY_OF]->(parent)
        """, items, "Disease 层级")

    def _create_syndrome_hierarchy(self) -> None:
        rows = self._query("SELECT code, parent_code FROM syndromes WHERE parent_code IS NOT NULL")
        items = [{"code": r["code"], "parent": r["parent_code"]} for r in rows]
        self._batch_write("""
            UNWIND $batch AS row
            MATCH (child:Syndrome {code: row.code})
            MATCH (parent:Syndrome {code: row.parent})
            MERGE (child)-[:SUBCATEGORY_OF]->(parent)
        """, items, "Syndrome 层级")

    def _create_disease_symptom_relations(self) -> None:
        pairs = []
        if self._has_diag_tables:
            rows = self._query("""
                SELECT d.name AS disease_name, s.name AS symptom_name
                FROM dictionary_diag_dic_ch_diag_comparison c
                JOIN dictionary_diag_dic_ch_diag_dictionary d ON c.ch_diag_dictionary_id = d.id
                JOIN dictionary_diag_dic_sym_dictionary s ON c.sym_dictionary_id = s.id
                WHERE d.name IS NOT NULL AND s.name IS NOT NULL
            """)
            pairs = [{"disease": r["disease_name"], "symptom": r["symptom_name"]} for r in rows]
            self._batch_write("""
                UNWIND $batch AS row
                MATCH (d:Disease {name: row.disease})
                MATCH (s:Symptom {name: row.symptom})
                MERGE (d)-[:HAS_SYMPTOM]->(s)
            """, pairs, "Disease → Symptom (结构化)")

        # 正则兜底
        if self._has_diag_tables:
            fallback_rows = self._query("""
                SELECT code, definition FROM diseases
                WHERE name NOT IN (SELECT name FROM dictionary_diag_dic_ch_diag_dictionary WHERE name IS NOT NULL)
            """)
        else:
            fallback_rows = self._query("SELECT code, definition FROM diseases")
        fb_pairs = []
        for r in fallback_rows:
            for s in self._extract_symptoms(r.get("definition", "")):
                fb_pairs.append({"code": r["code"], "symptom": s})
        if fb_pairs:
            self._batch_write("""
                UNWIND $batch AS row
                MATCH (d:Disease {code: row.code})
                MERGE (s:Symptom {name: row.symptom})
                MERGE (d)-[:HAS_SYMPTOM]->(s)
            """, fb_pairs, "Disease → Symptom (正则兜底)")

    def _create_syndrome_symptom_relations(self) -> None:
        rows = self._query("SELECT code, definition FROM syndromes")
        pairs = []
        for r in rows:
            for s in self._extract_symptoms(r.get("definition", "")):
                pairs.append({"code": r["code"], "symptom": s})
        self._batch_write("""
            UNWIND $batch AS row
            MATCH (s:Syndrome {code: row.code})
            MERGE (sym:Symptom {name: row.symptom})
            MERGE (s)-[:HAS_SYMPTOM]->(sym)
        """, pairs, "Syndrome → Symptom")

    def _create_formula_disease_relations(self) -> None:
        rows = self._query("SELECT name, clinical_use FROM formulas")
        diseases = self._query("SELECT name FROM diseases")
        disease_names = {d["name"] for d in diseases if len(d["name"]) >= 2}
        pairs = []
        for r in rows:
            clinical = r.get("clinical_use", "")
            for dn in disease_names:
                if dn in clinical:
                    pairs.append({"formula": r["name"], "disease": dn})
        self._batch_write("""
            UNWIND $batch AS row
            MATCH (f:Formula {name: row.formula})
            MATCH (d:Disease {name: row.disease})
            MERGE (f)-[:TREATS]->(d)
        """, pairs, "Formula → Disease")

    # ═══════════════════════════════════════
    #  关系创建 — 诊疗词典（已批量）
    # ═══════════════════════════════════════

    def _create_symptom_comparison_relations(self, batch_size: int = 5000) -> None:
        sql = """
            SELECT m.name AS main_name, s.name AS accomp_name
            FROM dictionary_diag_dic_sym_comparison c
            JOIN dictionary_diag_dic_sym_dictionary m ON c.main_sym_dictionary_id = m.id
            JOIN dictionary_diag_dic_sym_dictionary s ON c.sym_dictionary_id = s.id
            WHERE m.name IS NOT NULL AND s.name IS NOT NULL
        """
        query = """
            UNWIND $batch AS row
            MATCH (s1:Symptom {name: row.main})
            MATCH (s2:Symptom {name: row.accomp})
            MERGE (s1)-[:OFTEN_WITH]->(s2)
        """
        total = 0
        with self._conn.cursor() as cur:
            cur.execute(sql)
            while True:
                batch = cur.fetchmany(batch_size)
                if not batch:
                    break
                batch_data = [{"main": r["main_name"], "accomp": r["accomp_name"]} for r in batch]
                self.store.execute_write(query, {"batch": batch_data})
                total += len(batch)
                print(f"\r    ...{total}", end="", flush=True)
        print(f"\r  ✓ Symptom -[:OFTEN_WITH]-> Symptom: {total}{'':20}")

    # ═══════════════════════════════════════
    #  解析工具
    # ═══════════════════════════════════════

    def _parse_nature_taste_meridian(self, text: str) -> Tuple[str, str, str]:
        nature = taste = meridian = ""
        if not text:
            return nature, taste, meridian
        parts = text.replace("。", "：").split("：")
        if len(parts) >= 1:
            nature_taste = parts[0].strip()
            if "，" in nature_taste or "、" in nature_taste:
                items = re.split(r"[，,、]", nature_taste)
                four_qi = {"寒", "热", "温", "凉", "平", "大热", "微温", "微寒", "大寒"}
                tastes = [i.strip() for i in items if i.strip() and i.strip() not in four_qi
                          and not i.strip().endswith(("寒", "热", "温", "凉"))]
                natures = [i.strip() for i in items if i.strip() and (i.strip() in four_qi or i.strip().endswith(("寒", "热", "温", "凉")))]
                nature = "、".join(natures) if natures else (items[-1].strip() if items else "")
                taste = "、".join(tastes) if tastes else nature_taste
            else:
                taste = nature_taste
        if len(parts) >= 2:
            meridian = parts[1].strip().replace("归", "").replace("经", "").strip()
        return nature, taste, meridian

    def _split_meridians(self, text: str) -> List[str]:
        return [i.strip() for i in re.split(r"[，,、]", text) if i.strip()]

    def _split_nature(self, text: str) -> List[str]:
        return [i.strip() for i in re.split(r"[，,、]", text) if i.strip()]

    def _extract_symptoms(self, text: str) -> List[str]:
        """从文本中提取症状关键词

        优先用诊疗词典的症状名做匹配（召回率高）；
        诊疗词典不存在时回退到硬编码关键词。
        """
        if not text:
            return []
        if self._symptom_names is None:
            self._symptom_names = self._load_symptom_names()
        if self._symptom_names:
            found = set()
            for name in self._symptom_names:
                if name in text:
                    found.add(name)
            return list(found)
        return self._extract_symptoms_fallback(text)

    def _load_symptom_names(self) -> list[str]:
        """从 MySQL 加载症状名（按长度降序，优先匹配长词）"""
        if not self._has_diag_tables:
            return []
        try:
            rows = self._query("""
                SELECT DISTINCT name FROM dictionary_diag_dic_sym_dictionary
                WHERE name IS NOT NULL AND name != '' AND CHAR_LENGTH(name) >= 2
                ORDER BY CHAR_LENGTH(name) DESC
            """)
            names = [r["name"] for r in rows]
            print(f"  [INFO] 加载 {len(names)} 个症状名用于文本匹配")
            return names
        except Exception:
            return []

    def _extract_symptoms_fallback(self, text: str) -> List[str]:
        """硬编码关键词兜底（诊疗词典不存在时使用）"""
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
            "流涕", "喷嚏", "喉痒",
            "骨节痛", "四肢痛", "身痛", "项强",
            "面色晦暗", "唇甲色淡",
            "皮肤瘙痒", "皮疹", "湿疹",
            "吐血", "咯血",
            "五心烦热", "潮热",
            "目睛干涩", "视物模糊",
            "经行腹痛",
            "舌淡", "舌红", "苔白", "苔黄", "脉浮", "脉紧", "脉弦", "脉细",
        ]
        found = set()
        for kw in keywords:
            if kw in text:
                found.add(kw)
        return list(found)

    def close(self) -> None:
        self._conn.close()
