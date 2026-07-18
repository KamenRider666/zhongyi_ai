"""一键初始化全部数据

流水线:
  ① .txt → JSONL    (LLM 解析，可选跳过)
  ② JSONL → MySQL    (seedmysql.py)
  ③ MySQL → Neo4j    (graph_builder.py，统一构建器)
  ④ MySQL → Qdrant   (import_to_qdrant.py，6 类数据)

用法:
    # 全量初始化（含 LLM 解析，耗时很长）
    uv run python scripts/init_data.py

    # 跳过解析（JSONL 已存在）
    uv run python scripts/init_data.py --skip-parse

    # 只重建图谱
    uv run python scripts/init_data.py --skip-parse --skip-mysql --skip-qdrant

    # 只重建向量库
    uv run python scripts/init_data.py --skip-parse --skip-mysql --skip-graph

    # Qdrant 只导常用症状
    uv run python scripts/init_data.py --skip-parse --skip-graph --common-symptoms-only
"""

import argparse
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import settings


def step_parse():
    """① .txt → JSONL（纯代码解析，无需 LLM）"""
    print("=" * 60)
    print("[1/4] 解析 .txt → JSONL")
    print("=" * 60)

    from src.graphrag.parsers.parse_herbs import main as run_herbs
    from src.graphrag.parsers.parse_diseases import main as run_diseases
    from src.graphrag.parsers.parse_syndromes import main as run_syndromes
    from src.graphrag.parsers.parse_formulas import main as run_formulas

    print("\n--- 解析药材 ---")
    run_herbs()
    print("\n--- 解析疾病 ---")
    run_diseases()
    print("\n--- 解析证候 ---")
    run_syndromes()
    print("\n--- 解析方剂 ---")
    run_formulas()


def step_mysql():
    """② JSONL → MySQL"""
    print("\n" + "=" * 60)
    print("[2/4] JSONL → MySQL")
    print("=" * 60)

    from src.graphrag.seedmysql import init_all
    init_all()


def step_seed_aux():
    """初始化穴位、体质表数据（acupoint/constitution）

    这两张表由 TCMDatabase 管理，供图谱 Acupoint/Constitution 节点
    及 search_acupoint/search_constitution 工具使用。幂等（INSERT IGNORE）。
    """
    print("\n" + "=" * 60)
    print("[2.5/4] 初始化穴位、体质表数据")
    print("=" * 60)

    from src.data.database import TCMDatabase
    from src.data.seed import init_acupoint_data, init_constitution_data

    db = TCMDatabase()
    db.init_db()  # 确保表结构存在
    init_acupoint_data(db)
    init_constitution_data(db)
    print("✓ 穴位、体质表数据就绪")


def step_graph():
    """③ MySQL → Neo4j"""
    print("\n" + "=" * 60)
    print("[3/4] MySQL → Neo4j 知识图谱")
    print("=" * 60)

    from src.graphrag.graph_store import Neo4jGraphStore
    from src.graphrag.graph_builder import TCMGraphBuilder

    graph_store = Neo4jGraphStore(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
    )
    graph_store.connect()
    print("Neo4j 连接成功")

    builder = TCMGraphBuilder(graph_store)
    try:
        builder.build_full_graph()
    finally:
        builder.close()
        graph_store.close()


def step_qdrant(common_symptoms_only=False, reset=False):
    """④ MySQL → Qdrant"""
    print("\n" + "=" * 60)
    print("[4/4] MySQL → Qdrant 向量库")
    print("=" * 60)

    from scripts.import_to_qdrant import import_from_mysql, CATEGORY_CONFIG

    import_from_mysql(
        categories=list(CATEGORY_CONFIG.keys()),
        reset=reset,
        common_symptoms_only=common_symptoms_only,
    )


def main():
    parser = argparse.ArgumentParser(description="一键初始化全部数据")
    parser.add_argument("--skip-parse", action="store_true", help="跳过 LLM 解析步骤")
    parser.add_argument("--skip-mysql", action="store_true", help="跳过 MySQL 导入步骤")
    parser.add_argument("--skip-graph", action="store_true", help="跳过 Neo4j 图谱构建")
    parser.add_argument("--skip-qdrant", action="store_true", help="跳过 Qdrant 向量导入")
    parser.add_argument("--common-symptoms-only", action="store_true", help="Qdrant 只导常用症状")
    parser.add_argument("--reset-qdrant", action="store_true", help="先清空 Qdrant 集合")
    args = parser.parse_args()

    print("=" * 60)
    print("中医 AI 数据初始化")
    print(f"  MySQL:  {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}")
    print(f"  Neo4j:  {settings.NEO4J_URI}")
    print(f"  Qdrant: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    print("=" * 60)

    if not args.skip_parse:
        step_parse()
    else:
        print("[1/4] 跳过 LLM 解析")

    if not args.skip_mysql:
        step_mysql()
    else:
        print("[2/4] 跳过 MySQL 导入")

    step_seed_aux()

    if not args.skip_graph:
        step_graph()
    else:
        print("[3/4] 跳过图谱构建")

    if not args.skip_qdrant:
        step_qdrant(
            common_symptoms_only=args.common_symptoms_only,
            reset=args.reset_qdrant,
        )
    else:
        print("[4/4] 跳过 Qdrant 导入")

    print("\n" + "=" * 60)
    print("✓ 数据初始化完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
