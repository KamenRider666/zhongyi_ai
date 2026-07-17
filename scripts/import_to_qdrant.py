"""从 MySQL 读取中医知识，导入 Qdrant 向量库

数据源：MySQL agenttest 库（统一数据源）
  - herbs                                中药材
  - formulas                             方剂/中成药
  - diseases                             疾病（国标）
  - syndromes                            证候（国标）
  - dictionary_diag_dic_sym_dictionary   症状（诊疗词典，32766条）
  - dictionary_diag_dic_ch_therapy_dictionary  治法（诊疗词典，1168条）

用法:
    uv run python scripts/import_to_qdrant.py                  # 导入全部 6 类
    uv run python scripts/import_to_qdrant.py --category herb   # 只导入药材
    uv run python scripts/import_to_qdrant.py --reset           # 先清空集合再导入
    uv run python scripts/import_to_qdrant.py --skip-symptoms   # 跳过症状（量大耗时）
"""

import argparse
import json
import os
import sys

import pymysql
from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import settings
from src.rag.embedding import DashScopeEmbedding
from src.rag.qdrant_store import QdrantStore


# ═══════════════════════════════════════
#  MySQL 读取
# ═══════════════════════════════════════

def get_mysql_conn():
    return pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=settings.MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def query_table(table: str, columns: str = "*") -> list[dict]:
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {columns} FROM {table}")
            return cur.fetchall()
    finally:
        conn.close()


# ═══════════════════════════════════════
#  格式化函数（MySQL dict → 检索文本）
# ═══════════════════════════════════════

def format_herb(r: dict) -> str:
    parts = []
    if r.get("name"):
        parts.append(f"【药名】{r['name']}")
    if r.get("nature_taste_meridian"):
        parts.append(f"【性味归经】{r['nature_taste_meridian']}")
    if r.get("functions"):
        parts.append(f"【功能主治】{r['functions']}")
    if r.get("usage"):
        parts.append(f"【用法用量】{r['usage']}")
    if r.get("caution"):
        parts.append(f"【注意事项】{r['caution']}")
    if r.get("source"):
        parts.append(f"【来源】{r['source']}")
    return "\n".join(parts)


def format_formula(r: dict) -> str:
    parts = []
    if r.get("name"):
        parts.append(f"【方名】{r['name']}")
    if r.get("category"):
        parts.append(f"【分类】{r['category']}")
    if r.get("ingredients"):
        parts.append(f"【组成】{r['ingredients']}")
    if r.get("functions"):
        parts.append(f"【功能主治】{r['functions']}")
    if r.get("analysis"):
        analysis = r["analysis"].removeprefix("【方解】").strip()
        parts.append(f"【方解】{analysis}")
    if r.get("clinical_use"):
        clinical = r["clinical_use"].removeprefix("【临床应用】").strip()
        parts.append(f"【临床应用】{clinical}")
    return "\n".join(parts)


def format_disease(r: dict) -> str:
    if r.get("is_category"):
        return ""  # 跳过纯分类节点
    parts = []
    if r.get("name"):
        parts.append(f"【名称】{r['name']}")
    aliases = r.get("aliases")
    if isinstance(aliases, str):
        try:
            aliases = json.loads(aliases)
        except json.JSONDecodeError:
            aliases = []
    if isinstance(aliases, list) and len(aliases) > 0:
        parts.append(f"【别名】{'、'.join(aliases)}")
    if r.get("definition"):
        parts.append(f"【定义】{r['definition']}")
    if r.get("code"):
        parts.append(f"【编码】{r['code']}")
    return "\n".join(parts)


def format_syndrome(r: dict) -> str:
    if r.get("is_category"):
        return ""
    parts = []
    if r.get("name"):
        parts.append(f"【名称】{r['name']}")
    aliases = r.get("aliases")
    if isinstance(aliases, str):
        try:
            aliases = json.loads(aliases)
        except json.JSONDecodeError:
            aliases = []
    if isinstance(aliases, list) and len(aliases) > 0:
        parts.append(f"【别名】{'、'.join(aliases)}")
    if r.get("definition"):
        parts.append(f"【定义】{r['definition']}")
    if r.get("code"):
        parts.append(f"【编码】{r['code']}")
    return "\n".join(parts)


def format_symptom(r: dict) -> str:
    parts = []
    if r.get("name"):
        parts.append(f"【症状】{r['name']}")
    if r.get("dic_describe"):
        parts.append(f"【描述】{r['dic_describe']}")
    if r.get("directivity"):
        parts.append(f"【指向】{r['directivity']}")
    if r.get("common_sign") == "1":
        parts.append("【常用】是")
    if r.get("main_sign") == "1":
        parts.append("【主证】是")
    return "\n".join(parts)


def format_therapy(r: dict) -> str:
    parts = []
    if r.get("name"):
        parts.append(f"【治法】{r['name']}")
    if r.get("dic_describe"):
        parts.append(f"【描述】{r['dic_describe']}")
    if r.get("directivity"):
        parts.append(f"【指向】{r['directivity']}")
    return "\n".join(parts)


# ═══════════════════════════════════════
#  类别配置：类别 → (MySQL表名, 格式化函数)
# ═══════════════════════════════════════

CATEGORY_CONFIG = {
    "herb":     ("herbs",                                     format_herb),
    "formula":  ("formulas",                                  format_formula),
    "disease":  ("diseases",                                  format_disease),
    "syndrome": ("syndromes",                                 format_syndrome),
    "symptom":  ("dictionary_diag_dic_sym_dictionary",        format_symptom),
    "therapy":  ("dictionary_diag_dic_ch_therapy_dictionary", format_therapy),
}


# ═══════════════════════════════════════
#  导入逻辑
# ═══════════════════════════════════════

def import_from_mysql(
    categories: list[str],
    reset: bool = False,
    batch_size: int = 10,
    common_symptoms_only: bool = False,
) -> None:
    print("=" * 60)
    print("中医知识库导入 Qdrant (MySQL 模式)")
    print(f"  MySQL: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}")
    print("=" * 60)

    emb = DashScopeEmbedding(dimension=1024)
    store = QdrantStore(dim=1024)
    store.connect()

    print(f"  Qdrant:  {settings.QDRANT_HOST}:{settings.QDRANT_PORT}  →  {store.collection_name}")

    if reset and store.collection_exists():
        print("\n[WARN] 删除已有集合...")
        store.delete_collection()

    store.create_collection()

    total_chunks = 0
    global_id = 0

    for category in categories:
        table, formatter = CATEGORY_CONFIG[category]
        print(f"\n[{category.upper()}] 表: {table}")

        # 读取数据
        if category == "symptom" and common_symptoms_only:
            conn = get_mysql_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT * FROM {table} WHERE name IS NOT NULL AND name != '' AND common_sign = '1'"
                    )
                    rows = cur.fetchall()
            finally:
                conn.close()
        else:
            rows = query_table(table)

        if not rows:
            print(f"   → 无数据，跳过")
            continue

        # 格式化
        texts = []
        metadata = []
        skipped = 0

        for r in rows:
            text = formatter(r)
            if not text.strip():
                skipped += 1
                continue
            texts.append(text)
            meta = {k: v for k, v in r.items() if v is not None}
            metadata.append(meta)

        valid = len(texts)
        print(f"   → {valid} 条有效记录" + (f"（跳过 {skipped} 条）" if skipped else ""))

        if not texts:
            continue

        # 批量嵌入 + 存储
        for i in tqdm(range(0, valid, batch_size), desc="  嵌入 & 存储"):
            batch_texts = texts[i:i + batch_size]
            batch_meta = metadata[i:i + batch_size]
            batch_cat = [category] * len(batch_texts)
            batch_src = [table] * len(batch_texts)

            try:
                batch_emb = emb.encode(batch_texts)
            except Exception as e:
                print(f"\n   [ERROR] 嵌入失败 (记录 {i}-{i + len(batch_texts)}): {e}")
                continue

            store.insert(
                texts=batch_texts,
                embeddings=batch_emb,
                sources=batch_src,
                categories=batch_cat,
                id_start=global_id,
                metadata=batch_meta,
            )
            global_id += len(batch_texts)

        total_chunks += valid

    stats = store.get_stats()
    store.disconnect()

    print("\n" + "=" * 60)
    print(f"[OK] 导入完成！共 {total_chunks} 条记录存入 Qdrant")
    print(f"   统计: {stats['points']} 个向量")
    print("=" * 60)


# ═══════════════════════════════════════
#  CLI
# ═══════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 MySQL 导入中医知识到 Qdrant")
    parser.add_argument(
        "--category", type=str, default=None,
        choices=list(CATEGORY_CONFIG.keys()),
        help="只导入指定类别（默认全部 6 类）",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="先清空已有集合再导入",
    )
    parser.add_argument(
        "--skip-symptoms", action="store_true",
        help="跳过症状导入（32766条，量大耗时）",
    )
    parser.add_argument(
        "--common-symptoms-only", action="store_true",
        help="只导入常用症状（common_sign=1）",
    )
    args = parser.parse_args()

    if args.category:
        cats = [args.category]
    else:
        cats = list(CATEGORY_CONFIG.keys())
        if args.skip_symptoms:
            cats = [c for c in cats if c != "symptom"]

    import_from_mysql(
        categories=cats,
        reset=args.reset,
        common_symptoms_only=args.common_symptoms_only,
    )
