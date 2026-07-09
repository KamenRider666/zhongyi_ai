"""知识图谱种子数据初始化 - 从 SQLite 数据构建 Neo4j 知识图谱"""

import sys
import io

# 修复 Windows GBK 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from src.config import settings
from src.data.database import TCMDatabase
from src.graphrag.graph_store import Neo4jGraphStore
from src.graphrag.graph_builder import TCMGraphBuilder


def init_graph_data(
    db_path: str = "data/tcm.db",
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "zhongyi2024",
) -> None:
    """初始化知识图谱数据"""
    print("🔗 连接 Neo4j...")
    graph_store = Neo4jGraphStore(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password,
    )
    graph_store.connect()
    print("✓ Neo4j 连接成功")

    print("📦 加载 SQLite 数据...")
    tcm_db = TCMDatabase(db_path)

    print("🏗️ 构建知识图谱...")
    builder = TCMGraphBuilder(graph_store, tcm_db)
    builder.build_full_graph()

    stats = graph_store.get_stats()
    print(f"\n✓ 知识图谱初始化完成:")
    print(f"  - 节点数: {stats['nodes']}")
    print(f"  - 关系数: {stats['relationships']}")

    graph_store.close()


if __name__ == "__main__":
    init_graph_data(
        db_path=settings.SQLITE_PATH,
        neo4j_uri=settings.NEO4J_URI,
        neo4j_user=settings.NEO4J_USER,
        neo4j_password=settings.NEO4J_PASSWORD,
    )
