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

    # === SQLite ===
    SQLITE_PATH: str = "data/tcm.db"

    # === 服务 ===
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
