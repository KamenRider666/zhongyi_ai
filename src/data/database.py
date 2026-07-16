"""数据库管理 - 支持 MySQL 和 SQLite（通过 DB_TYPE 配置切换，默认 mysql）"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import pymysql
from pymysql.cursors import DictCursor

from src.config import settings


class TCMDatabase:
    """中医结构化数据库

    用法:
        # 使用默认配置（默认 MySQL）
        db = TCMDatabase()

        # 显式指定 SQLite
        db = TCMDatabase(db_type="sqlite", db_path="data/tcm.db")

        # 显式指定 MySQL
        db = TCMDatabase(db_type="mysql", host="127.0.0.1", port=3306, ...)
    """

    def __init__(
        self,
        db_type: Optional[str] = None,
        *,
        # ── SQLite ──
        db_path: Optional[str] = None,
        # ── MySQL ──
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self.db_type = db_type or settings.DB_TYPE
        self.db_path = db_path or settings.SQLITE_PATH
        self.host = host or settings.MYSQL_HOST
        self.port = port or settings.MYSQL_PORT
        self.user = user or settings.MYSQL_USER
        self.password = password or settings.MYSQL_PASSWORD
        self.database = database or settings.MYSQL_DATABASE

        if self.db_type == "sqlite":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        if self.db_type == "sqlite":
            return f"TCMDatabase(sqlite, {self.db_path})"
        return f"TCMDatabase(mysql, {self.user}@{self.host}:{self.port}/{self.database})"

    # ──────────────────────────────────────────────
    #  内部工具
    # ──────────────────────────────────────────────

    @property
    def _ph(self) -> str:
        """参数占位符: SQLite 用 ?, MySQL 用 %s"""
        return "?" if self.db_type == "sqlite" else "%s"

    @property
    def _insert_ignore(self) -> str:
        """INSERT 忽略重复语法"""
        return "INSERT OR IGNORE" if self.db_type == "sqlite" else "INSERT IGNORE"

    def get_conn(self):
        """获取数据库连接"""
        if self.db_type == "sqlite":
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
        else:
            conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4",
                cursorclass=DictCursor,
            )
        return conn

    def _exec_sql(self, sql: str, *args: Any) -> None:
        """执行写操作，自动 commit + close"""
        conn = self.get_conn()
        conn.cursor().execute(sql, args)
        conn.commit()
        conn.close()

    # ──────────────────────────────────────────────
    #  建表
    # ──────────────────────────────────────────────

    _TABLE_SUFFIX: Dict[str, str] = {
        "sqlite": "",
        "mysql": " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
    }

    def init_db(self) -> None:
        """初始化数据库表结构"""
        ph = self._ph
        suffix = self._TABLE_SUFFIX[self.db_type]

        self._exec_sql(f"""
            CREATE TABLE IF NOT EXISTS fangji (
                id {"INTEGER PRIMARY KEY AUTOINCREMENT" if self.db_type == "sqlite" else "INT AUTO_INCREMENT PRIMARY KEY"},
                name VARCHAR(200) NOT NULL UNIQUE,
                alias VARCHAR(200),
                source VARCHAR(200) NOT NULL,
                category VARCHAR(100) NOT NULL,
                composition TEXT NOT NULL,
                usage_method TEXT,
                efficacy TEXT NOT NULL,
                indications TEXT NOT NULL,
                contraindications TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ){suffix}
        """)

        self._exec_sql(f"""
            CREATE TABLE IF NOT EXISTS herb (
                id {"INTEGER PRIMARY KEY AUTOINCREMENT" if self.db_type == "sqlite" else "INT AUTO_INCREMENT PRIMARY KEY"},
                name VARCHAR(200) NOT NULL UNIQUE,
                latin_name VARCHAR(200),
                alias VARCHAR(200),
                nature VARCHAR(50) NOT NULL,
                taste VARCHAR(100) NOT NULL,
                meridian VARCHAR(200) NOT NULL,
                efficacy TEXT NOT NULL,
                indications TEXT NOT NULL,
                dosage VARCHAR(100),
                toxicity VARCHAR(100),
                contraindications TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ){suffix}
        """)

        self._exec_sql(f"""
            CREATE TABLE IF NOT EXISTS acupoint (
                id {"INTEGER PRIMARY KEY AUTOINCREMENT" if self.db_type == "sqlite" else "INT AUTO_INCREMENT PRIMARY KEY"},
                name VARCHAR(200) NOT NULL UNIQUE,
                pinyin VARCHAR(200),
                meridian VARCHAR(200) NOT NULL,
                location TEXT NOT NULL,
                method VARCHAR(200) NOT NULL,
                efficacy TEXT NOT NULL,
                indications TEXT NOT NULL,
                technique VARCHAR(200),
                cautions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ){suffix}
        """)

        self._exec_sql(f"""
            CREATE TABLE IF NOT EXISTS constitution (
                id {"INTEGER PRIMARY KEY AUTOINCREMENT" if self.db_type == "sqlite" else "INT AUTO_INCREMENT PRIMARY KEY"},
                type_name VARCHAR(200) NOT NULL UNIQUE,
                characteristics TEXT NOT NULL,
                tendency TEXT,
                regulation TEXT NOT NULL,
                diet_advice TEXT,
                exercise_advice TEXT,
                acupoint_advice TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ){suffix}
        """)

    # ──────────────────────────────────────────────
    #  通用插入（seed.py 使用）
    # ──────────────────────────────────────────────

    def insert_ignore(self, table: str, columns: List[str], values: tuple) -> None:
        """忽略重复的插入，自动适配 SQLite/MySQL"""
        cols = ", ".join(columns)
        vals = ", ".join([self._ph] * len(columns))
        sql = f"{self._insert_ignore} INTO {table} ({cols}) VALUES ({vals})"
        self._exec_sql(sql, *values)

    # ──────────────────────────────────────────────
    #  方剂操作
    # ──────────────────────────────────────────────

    def search_fangji(
        self,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索方剂"""
        conn = self.get_conn()
        cursor = conn.cursor()
        ph = self._ph

        query = "SELECT * FROM formulas WHERE 1=1"
        params: List[Any] = []

        if keyword:
            query += f" AND (name LIKE {ph} OR functions LIKE {ph} OR clinical_use LIKE {ph})"
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        if category:
            query += f" AND category = {ph}"
            params.append(category)

        query += f" LIMIT {ph}"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_fangji_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取方剂"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM formulas WHERE name LIKE {self._ph}", (f"%{name}%",))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # ──────────────────────────────────────────────
    #  药材操作
    # ──────────────────────────────────────────────

    def search_herb(
        self,
        keyword: Optional[str] = None,
        nature: Optional[str] = None,
        meridian: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索药材"""
        conn = self.get_conn()
        cursor = conn.cursor()
        ph = self._ph

        query = "SELECT * FROM herbs WHERE 1=1"
        params: List[Any] = []

        if keyword:
            query += f" AND (name LIKE {ph} OR functions LIKE {ph})"
            kw = f"%{keyword}%"
            params.extend([kw, kw])
        if nature:
            query += f" AND nature_taste_meridian LIKE {ph}"
            params.append(f"%{nature}%")
        if meridian:
            query += f" AND nature_taste_meridian LIKE {ph}"
            params.append(f"%{meridian}%")

        query += f" LIMIT {ph}"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_herb_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取药材"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM herbs WHERE name LIKE {self._ph}", (f"%{name}%",))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # ──────────────────────────────────────────────
    #  穴位操作
    # ──────────────────────────────────────────────

    def search_acupoint(
        self,
        keyword: Optional[str] = None,
        meridian: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索穴位"""
        conn = self.get_conn()
        cursor = conn.cursor()
        ph = self._ph

        query = "SELECT * FROM acupoint WHERE 1=1"
        params: List[Any] = []

        if keyword:
            query += f" AND (name LIKE {ph} OR indications LIKE {ph})"
            kw = f"%{keyword}%"
            params.extend([kw, kw])
        if meridian:
            query += f" AND meridian = {ph}"
            params.append(meridian)

        query += f" LIMIT {ph}"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ──────────────────────────────────────────────
    #  体质操作
    # ──────────────────────────────────────────────

    def get_constitution(self, type_name: str) -> Optional[Dict[str, Any]]:
        """获取体质类型信息"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM constitution WHERE type_name LIKE {self._ph}", (f"%{type_name}%",))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_constitutions(self) -> List[Dict[str, Any]]:
        """列出所有体质类型"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM constitution")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
