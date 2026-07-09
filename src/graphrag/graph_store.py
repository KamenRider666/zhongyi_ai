"""Neo4j 图数据库连接与操作"""

from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase, Driver


class Neo4jGraphStore:
    """Neo4j 知识图谱存储封装"""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "zhongyi2024",
        database: str = "tcm_graph",
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver: Optional[Driver] = None

    def connect(self) -> None:
        """建立 Neo4j 连接"""
        self._driver = GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password),
        )
        # 验证连接
        self._driver.verify_connectivity()

    def close(self) -> None:
        """关闭连接"""
        if self._driver:
            self._driver.close()
            self._driver = None

    @property
    def driver(self) -> Driver:
        """获取驱动实例"""
        if self._driver is None:
            self.connect()
        return self._driver

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """执行 Cypher 查询并返回结果

        Args:
            query: Cypher 查询语句
            parameters: 查询参数

        Returns:
            查询结果列表
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """执行 Cypher 写操作

        Args:
            query: Cypher 写语句
            parameters: 写参数
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, parameters or {})

    def clear_graph(self) -> None:
        """清空知识图谱（删除所有节点和关系）"""
        self.execute_write("MATCH (n) DETACH DELETE n")
        print("✓ 知识图谱已清空")

    def get_stats(self) -> Dict[str, int]:
        """获取图谱统计信息"""
        node_count = self.execute_query(
            "MATCH (n) RETURN count(n) AS cnt"
        )[0]["cnt"]
        rel_count = self.execute_query(
            "MATCH ()-[r]->() RETURN count(r) AS cnt"
        )[0]["cnt"]
        return {"nodes": node_count, "relationships": rel_count}

    def create_constraints(self) -> None:
        """创建唯一性约束（确保节点不重复）"""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Formula) REQUIRE f.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (h:Herb) REQUIRE h.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Acupoint) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Constitution) REQUIRE c.type IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Symptom) REQUIRE s.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Meridian) REQUIRE m.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (cat:Category) REQUIRE cat.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Book) REQUIRE b.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (nat:Nature) REQUIRE nat.name IS UNIQUE",
        ]
        for constraint in constraints:
            self.execute_write(constraint)
