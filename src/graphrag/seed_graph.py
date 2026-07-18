"""知识图谱构建 - 从 MySQL 构建 Neo4j 知识图谱

数据源：MySQL agenttest 库 14 张表（4 项目表 + 10 诊疗词典表）
构建器：TCMGraphBuilder（批量 UNWIND 写入）

用法:
    # 直接构建（MERGE 更新，不清空旧数据）
    uv run python -m src.graphrag.seed_graph

    # 先清空旧图谱再构建（推荐，干净重建）
    uv run python -m src.graphrag.seed_graph --reset
"""

import sys
import io
import argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from src.config import settings
from src.graphrag.graph_store import Neo4jGraphStore
from src.graphrag.graph_builder import TCMGraphBuilder


def init_graph_data(reset: bool = False) -> None:
    print("连接 Neo4j...")
    graph_store = Neo4jGraphStore(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
    )
    graph_store.connect()
    print(f"Neo4j 连接成功: {settings.NEO4J_URI}")
    print(f"MySQL 源: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}")

    # 清空旧数据
    if reset:
        print("\n⚠️  清空已有图谱数据...")
        graph_store.clear_graph()

    # 构建
    builder = TCMGraphBuilder(graph_store)
    try:
        builder.build_full_graph()
    finally:
        builder.close()

    # 统计
    stats = graph_store.get_stats()
    print(f"\n知识图谱构建完成:")
    print(f"  节点数: {stats['nodes']}")
    print(f"  关系数: {stats['relationships']}")

    graph_store.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 MySQL 构建 Neo4j 知识图谱")
    parser.add_argument(
        "--reset", action="store_true",
        help="先清空已有图谱数据再构建（干净重建）",
    )
    args = parser.parse_args()

    init_graph_data(reset=args.reset)
