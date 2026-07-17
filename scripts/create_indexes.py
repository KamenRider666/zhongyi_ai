"""创建数据库索引 — MySQL + Neo4j + Qdrant

一次性运行，提升检索性能：
  - MySQL: name/parent_code/FK 字段加索引
  - Neo4j: Disease.name / Syndrome.name 加索引（code 已有约束）
  - Qdrant: category payload 索引（按类别过滤时加速）

用法:
    uv run python scripts/create_indexes.py
"""

import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import settings


# ═══════════════════════════════════════
#  MySQL 索引
# ═══════════════════════════════════════

MYSQL_INDEXES = [
    # 项目表 — name 和 parent_code 用于图谱构建时的 MATCH/MERGE
    ("diseases", "idx_disease_name", "name"),
    ("diseases", "idx_disease_parent", "parent_code"),
    ("syndromes", "idx_syndrome_name", "name"),
    ("syndromes", "idx_syndrome_parent", "parent_code"),

    # 诊疗词典 — name 用于 JOIN 和 MERGE
    ("dictionary_diag_dic_sym_dictionary", "idx_sym_name", "name"),
    ("dictionary_diag_dic_ch_diag_dictionary", "idx_chdiag_name", "name"),
    ("dictionary_diag_dic_ch_yndrome_dictionary", "idx_chyndrome_name", "name"),
    ("dictionary_diag_dic_ch_therapy_dictionary", "idx_therapy_name", "name"),

    # 对照表 — 外键用于 JOIN
    ("dictionary_diag_dic_ch_diag_comparison", "idx_diag_comp_diag", "ch_diag_dictionary_id"),
    ("dictionary_diag_dic_ch_diag_comparison", "idx_diag_comp_sym", "sym_dictionary_id"),
    ("dictionary_diag_dic_sym_comparison", "idx_sym_comp_main", "main_sym_dictionary_id"),
    ("dictionary_diag_dic_sym_comparison", "idx_sym_comp_sym", "sym_dictionary_id"),
]


def create_mysql_indexes():
    import pymysql

    print("=" * 50)
    print("[MySQL] 创建索引")
    print(f"  {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}")
    print("=" * 50)

    conn = pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=settings.MYSQL_DATABASE,
        charset="utf8mb4",
    )
    cursor = conn.cursor()

    for table, index_name, column in MYSQL_INDEXES:
        sql = f"CREATE INDEX IF NOT EXISTS `{index_name}` ON `{table}` (`{column}`)"
        try:
            cursor.execute(sql)
            print(f"  ✓ {table}.{column} → {index_name}")
        except Exception as e:
            # MySQL 8.0 以下不支持 IF NOT EXISTS，用 try-ignore
            if "Duplicate key name" in str(e):
                print(f"  ⊙ {table}.{column} → {index_name} (已存在)")
            else:
                # 表可能不存在（诊疗词典表）
                print(f"  ✗ {table}.{column} → {index_name}: {e}")

    conn.commit()
    conn.close()
    print()


# ═══════════════════════════════════════
#  Neo4j 索引
# ═══════════════════════════════════════

NEO4J_INDEXES = [
    # name 索引（code 已有 UNIQUE 约束自带索引）
    "CREATE INDEX IF NOT EXISTS FOR (d:Disease) ON (d.name)",
    "CREATE INDEX IF NOT EXISTS FOR (s:Syndrome) ON (s.name)",
    # diag_id 索引（用于诊疗词典数据关联）
    "CREATE INDEX IF NOT EXISTS FOR (s:Symptom) ON (s.diag_id)",
    # common_sign 索引（常用症状过滤）
    "CREATE INDEX IF NOT EXISTS FOR (s:Symptom) ON (s.common_sign)",
]


def create_neo4j_indexes():
    from src.graphrag.graph_store import Neo4jGraphStore

    print("=" * 50)
    print("[Neo4j] 创建索引")
    print(f"  {settings.NEO4J_URI}")
    print("=" * 50)

    store = Neo4jGraphStore(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
    )
    store.connect()

    for cypher in NEO4J_INDEXES:
        try:
            store.execute_write(cypher)
            # 提取标签和属性用于打印
            label = cypher.split("(:")[1].split(")")[0] if "(:)" not in cypher else "?"
            prop = cypher.split("ON (")[1].split(")")[0] if "ON (" in cypher else "?"
            print(f"  ✓ {label}.{prop}")
        except Exception as e:
            print(f"  ✗ {cypher}: {e}")

    store.close()
    print()


# ═══════════════════════════════════════
#  Qdrant payload 索引
# ═══════════════════════════════════════

def create_qdrant_indexes():
    from src.rag.qdrant_store import QdrantStore
    from qdrant_client import models

    print("=" * 50)
    print("[Qdrant] 创建 payload 索引")
    print(f"  {settings.QDRANT_HOST}:{settings.QDRANT_PORT}/{settings.QDRANT_COLLECTION}")
    print("=" * 50)

    store = QdrantStore(dim=1024)
    store.connect()

    if not store.collection_exists():
        print("  ⊙ 集合不存在，跳过（先导入数据再建索引）")
        store.disconnect()
        print()
        return

    # category 字段索引（按 herb/formula/disease 等类别过滤）
    try:
        store.client.create_payload_index(
            collection_name=store.collection_name,
            field_name="category",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        print("  ✓ category (keyword)")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("  ⊙ category (已存在)")
        else:
            print(f"  ✗ category: {e}")

    # source 字段索引（按来源表过滤）
    try:
        store.client.create_payload_index(
            collection_name=store.collection_name,
            field_name="source",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        print("  ✓ source (keyword)")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("  ⊙ source (已存在)")
        else:
            print(f"  ✗ source: {e}")

    store.disconnect()
    print()


# ═══════════════════════════════════════
#  主入口
# ═══════════════════════════════════════

def main():
    print()
    print("╔" + "═" * 48 + "╗")
    print("║" + "  数据库索引创建".center(46) + "║")
    print("╚" + "═" * 48 + "╝")
    print()

    create_mysql_indexes()
    create_neo4j_indexes()
    create_qdrant_indexes()

    print("✓ 全部索引创建完成")


if __name__ == "__main__":
    main()
