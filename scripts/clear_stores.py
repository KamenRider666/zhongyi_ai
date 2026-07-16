"""清空 Neo4j 和 Qdrant 存量数据，为新知识图谱做准备"""

import sys
import io
from pathlib import Path

# 修复 Windows GBK 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graphrag.graph_store import Neo4jGraphStore
from src.rag.qdrant_store import QdrantStore


def clear_all():
    # 1. 清空 Neo4j
    print("=" * 50)
    print("[1/2] 清空 Neo4j...")
    neo4j = Neo4jGraphStore()
    neo4j.connect()
    try:
        before = neo4j.get_stats()
        print(f"  当前: {before['nodes']} 节点, {before['relationships']} 关系")
        neo4j.clear_graph()
        after = neo4j.get_stats()
        print(f"  删除后: {after['nodes']} 节点, {after['relationships']} 关系")
    finally:
        neo4j.close()

    # 2. 清空 Qdrant
    print("[2/2] 清空 Qdrant...")
    qdrant = QdrantStore()
    qdrant.connect()
    try:
        stats = qdrant.get_stats()
        if stats["exists"]:
            print(f"  当前: {stats['points']} 条向量")
            qdrant.delete_collection()
            print(f"  collection 已删除")
        else:
            print(f"  collection 不存在, 无需清空")
    finally:
        qdrant.disconnect()

    print("=" * 50)
    print("DONE: Neo4j 和 Qdrant 已全部清空。")


if __name__ == "__main__":
    clear_all()
