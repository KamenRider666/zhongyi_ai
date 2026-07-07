"""SQLite 数据库管理 - 方剂、药材、穴位"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class TCMDatabase:
    """中医结构化数据库"""

    def __init__(self, db_path: str = "data/tcm.db"):
        self.db_path = db_path
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """初始化数据库表结构"""
        conn = self.get_conn()
        cursor = conn.cursor()

        # 方剂表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fangji (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                alias TEXT,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                composition TEXT NOT NULL,
                usage_method TEXT,
                efficacy TEXT NOT NULL,
                indications TEXT NOT NULL,
                contraindications TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 药材表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS herb (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                latin_name TEXT,
                alias TEXT,
                nature TEXT NOT NULL,
                taste TEXT NOT NULL,
                meridian TEXT NOT NULL,
                efficacy TEXT NOT NULL,
                indications TEXT NOT NULL,
                dosage TEXT,
                toxicity TEXT,
                contraindications TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 穴位表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS acupoint (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                pinyin TEXT,
                meridian TEXT NOT NULL,
                location TEXT NOT NULL,
                method TEXT NOT NULL,
                efficacy TEXT NOT NULL,
                indications TEXT NOT NULL,
                technique TEXT,
                cautions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 体质表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS constitution (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type_name TEXT NOT NULL UNIQUE,
                characteristics TEXT NOT NULL,
                tendency TEXT,
                regulation TEXT NOT NULL,
                diet_advice TEXT,
                exercise_advice TEXT,
                acupoint_advice TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    # === 方剂操作 ===

    def search_fangji(
        self,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索方剂"""
        conn = self.get_conn()
        cursor = conn.cursor()

        query = "SELECT * FROM fangji WHERE 1=1"
        params: List[Any] = []

        if keyword:
            query += " AND (name LIKE ? OR indications LIKE ? OR efficacy LIKE ?)"
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        if category:
            query += " AND category = ?"
            params.append(category)

        query += " LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_fangji_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取方剂"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM fangji WHERE name LIKE ?", (f"%{name}%",))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # === 药材操作 ===

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

        query = "SELECT * FROM herb WHERE 1=1"
        params: List[Any] = []

        if keyword:
            query += " AND (name LIKE ? OR efficacy LIKE ? OR indications LIKE ?)"
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        if nature:
            query += " AND nature LIKE ?"
            params.append(f"%{nature}%")
        if meridian:
            query += " AND meridian LIKE ?"
            params.append(f"%{meridian}%")

        query += " LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_herb_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取药材"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM herb WHERE name LIKE ?", (f"%{name}%",))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # === 穴位操作 ===

    def search_acupoint(
        self,
        keyword: Optional[str] = None,
        meridian: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索穴位"""
        conn = self.get_conn()
        cursor = conn.cursor()

        query = "SELECT * FROM acupoint WHERE 1=1"
        params: List[Any] = []

        if keyword:
            query += " AND (name LIKE ? OR indications LIKE ?)"
            kw = f"%{keyword}%"
            params.extend([kw, kw])
        if meridian:
            query += " AND meridian = ?"
            params.append(meridian)

        query += " LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # === 体质操作 ===

    def get_constitution(self, type_name: str) -> Optional[Dict[str, Any]]:
        """获取体质类型信息"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM constitution WHERE type_name LIKE ?", (f"%{type_name}%",))
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
