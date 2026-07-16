"""知识图谱种子数据初始化 - 从 MySQL 构建 Neo4j 知识图谱

适配 seedmysql.py 导入的 4 张新表:
  - formulas / herbs / diseases / syndromes
"""

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from src.config import settings
from src.graphrag.graph_store import Neo4jGraphStore
from src.graphrag.graph_builder import TCMGraphBuilder


def init_graph_data(
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "zhongyi2024",
) -> None:
    print("连接 Neo4j...")
    graph_store = Neo4jGraphStore(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password,
    )
    graph_store.connect()
    print("Neo4j 连接成功")

    print(f"目标库: {settings.MYSQL_USER}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}")

    builder = TCMGraphBuilder(graph_store)
    builder.build_full_graph()

    stats = graph_store.get_stats()
    print(f"\n知识图谱初始化完成:")
    print(f"  - 节点数: {stats['nodes']}")
    print(f"  - 关系数: {stats['relationships']}")

    builder.close()
    graph_store.close()


if __name__ == "__main__":
    init_graph_data(
        neo4j_uri=settings.NEO4J_URI,
        neo4j_user=settings.NEO4J_USER,
        neo4j_password=settings.NEO4J_PASSWORD,
    )
