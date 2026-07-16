"""应用配置 - 从环境变量加载"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置"""

    # === 通义千问 ===
    DASHSCOPE_API_KEY: str = ""
    QWEN_MODEL: str = "qwen-plus"

    # === Milvus ===
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "tcm_knowledge"

    # === 数据库 ===
    DB_TYPE: str = "mysql"           # "mysql" 或 "sqlite"
    SQLITE_PATH: str = "data/tcm.db"
    MYSQL_HOST: str = "192.168.31.120"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "dcdevtest"
    MYSQL_DATABASE: str = "agenttest"

    # === Neo4j ===
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "zhongyi2024"
    NEO4J_DATABASE: str = "neo4j"

    # === 服务 ===
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # === Qdrant（可选，替代 Milvus）===
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "tcm_knowledge"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
