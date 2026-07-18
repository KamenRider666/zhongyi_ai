"""种子数据初始化 - 将 /src/graphrag/jsonl 中四个 JSONL 文件导入 MySQL

四张表:
  - diseases   (疾病 - diseases_test.jsonl)
  - syndromes  (证候 - syndromes_test.jsonl)
  - herbs      (药材 - herbs_test.jsonl)
  - formulas   (方剂/中成药 - formulas_test.jsonl)

会先检查/创建对应表，再安全导入数据。
"""

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import pymysql

from src.config import settings

# ── JSONL 文件路径（统一从项目根 data/ 目录读取）──
HERE = os.path.dirname(os.path.abspath(__file__))
JSONL_DIR = os.path.join(HERE, "..", "..", "data")

FILE_MAP = {
    "diseases":  os.path.join(JSONL_DIR, "diseases.jsonl"),
    "syndromes": os.path.join(JSONL_DIR, "syndromes.jsonl"),
    "herbs":     os.path.join(JSONL_DIR, "herbs.jsonl"),
    "formulas":  os.path.join(JSONL_DIR, "formulas.jsonl"),
}


# ═══════════════════════════════════════════════
#  MySQL 连接
# ═══════════════════════════════════════════════

def get_conn():
    """获取 MySQL 连接"""
    return pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=settings.MYSQL_DATABASE,
        charset="utf8mb4",
    )


def exec_ddl(sql: str) -> None:
    """执行 DDL（建表），自动 commit + close"""
    conn = get_conn()
    conn.cursor().execute(sql)
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════
#  建表（CREATE TABLE IF NOT EXISTS）
# ═══════════════════════════════════════════════

def create_tables() -> None:
    """创建四张表（如果不存在）"""
    print("检查并创建数据库表...")

    # ── diseases ──
    exec_ddl("""
        CREATE TABLE IF NOT EXISTS diseases (
            id      INT AUTO_INCREMENT PRIMARY KEY,
            code    VARCHAR(50)   NOT NULL,
            name    VARCHAR(200)  NOT NULL,
            aliases JSON          COMMENT '别名列表',
            definition TEXT       COMMENT '疾病定义',
            is_category TINYINT(1)  DEFAULT 0  COMMENT '是否分类节点',
            parent_code VARCHAR(50)           COMMENT '父级 code',
            created_at TIMESTAMP  DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_code (code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("  ✓ diseases")

    # ── syndromes ──
    exec_ddl("""
        CREATE TABLE IF NOT EXISTS syndromes (
            id      INT AUTO_INCREMENT PRIMARY KEY,
            code    VARCHAR(50)   NOT NULL,
            name    VARCHAR(200)  NOT NULL,
            aliases JSON          COMMENT '别名列表',
            definition TEXT       COMMENT '证候定义',
            is_category TINYINT(1)  DEFAULT 0  COMMENT '是否分类节点',
            parent_code VARCHAR(50)           COMMENT '父级 code',
            created_at TIMESTAMP  DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_code (code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("  ✓ syndromes")

    # ── herbs ──
    exec_ddl("""
        CREATE TABLE IF NOT EXISTS herbs (
            id      INT AUTO_INCREMENT PRIMARY KEY,
            name    VARCHAR(200)  NOT NULL,
            pinyin  VARCHAR(200),
            latin_name VARCHAR(200),
            source  TEXT,
            properties TEXT,
            identification TEXT,
            processing TEXT,
            nature_taste_meridian TEXT,
            functions TEXT,
            `usage` VARCHAR(200),
            caution TEXT,
            storage VARCHAR(200),
            is_appendix TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP  DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("  ✓ herbs")

    # ── formulas ──
    exec_ddl("""
        CREATE TABLE IF NOT EXISTS formulas (
            id      INT AUTO_INCREMENT PRIMARY KEY,
            name    VARCHAR(200)  NOT NULL,
            pinyin  VARCHAR(200),
            category VARCHAR(100),
            ingredients TEXT,
            functions   TEXT,
            analysis    TEXT,
            clinical_use TEXT,
            pharmacology TEXT,
            adverse_reactions TEXT,
            contraindications TEXT,
            precautions TEXT,
            `usage`  VARCHAR(200),
            specs    VARCHAR(200),
            `references` JSON,
            created_at TIMESTAMP  DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("  ✓ formulas")
    print("建表完成\n")


# ═══════════════════════════════════════════════
#  数据导入（executemany 批量插入）
# ═══════════════════════════════════════════════

BATCH_SIZE = 1000


def load_jsonl(filepath: str) -> list[dict]:
    """读取 JSONL 文件，返回 dict 列表"""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _batch_insert(cursor, sql: str, rows: list[tuple]) -> int:
    """批量插入，每 BATCH_SIZE 条提交一次"""
    count = 0
    total = len(rows)
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        cursor.executemany(sql, batch)
        count += len(batch)
        print(f"    ...{count}/{total}")
    return count


def import_diseases() -> int:
    """导入疾病表"""
    filepath = FILE_MAP["diseases"]
    print(f"  读取 {filepath}")
    records = load_jsonl(filepath)
    print(f"  共 {len(records)} 条，开始导入...")

    conn = get_conn()
    cursor = conn.cursor()
    sql = """
        INSERT IGNORE INTO diseases
            (code, name, aliases, definition, is_category, parent_code)
        VALUES
            (%s, %s, %s, %s, %s, %s)
    """
    rows = [(
        r.get("code"),
        r.get("name"),
        json.dumps(r.get("aliases", []), ensure_ascii=False),
        r.get("definition"),
        1 if r.get("is_category") else 0,
        r.get("parent_code"),
    ) for r in records]
    count = _batch_insert(cursor, sql, rows)
    conn.commit()
    conn.close()
    return count


def import_syndromes() -> int:
    """导入证候表"""
    filepath = FILE_MAP["syndromes"]
    print(f"  读取 {filepath}")
    records = load_jsonl(filepath)
    print(f"  共 {len(records)} 条，开始导入...")

    conn = get_conn()
    cursor = conn.cursor()
    sql = """
        INSERT IGNORE INTO syndromes
            (code, name, aliases, definition, is_category, parent_code)
        VALUES
            (%s, %s, %s, %s, %s, %s)
    """
    rows = [(
        r.get("code"),
        r.get("name"),
        json.dumps(r.get("aliases", []), ensure_ascii=False),
        r.get("definition"),
        1 if r.get("is_category") else 0,
        r.get("parent_code"),
    ) for r in records]
    count = _batch_insert(cursor, sql, rows)
    conn.commit()
    conn.close()
    return count


def import_herbs() -> int:
    """导入药材表"""
    filepath = FILE_MAP["herbs"]
    print(f"  读取 {filepath}")
    records = load_jsonl(filepath)
    print(f"  共 {len(records)} 条，开始导入...")

    conn = get_conn()
    cursor = conn.cursor()
    sql = """
        INSERT IGNORE INTO herbs
            (name, pinyin, latin_name, source, properties, identification,
             processing, nature_taste_meridian, functions, `usage`, caution, storage, is_appendix)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    rows = [(
        r.get("name"),
        r.get("pinyin"),
        r.get("latin_name"),
        r.get("source"),
        r.get("properties"),
        r.get("identification"),
        r.get("processing"),
        r.get("nature_taste_meridian"),
        r.get("functions"),
        r.get("usage"),
        r.get("caution"),
        r.get("storage"),
        1 if r.get("is_appendix") else 0,
    ) for r in records]
    count = _batch_insert(cursor, sql, rows)
    conn.commit()
    conn.close()
    return count


def import_formulas() -> int:
    """导入方剂表"""
    filepath = FILE_MAP["formulas"]
    print(f"  读取 {filepath}")
    records = load_jsonl(filepath)
    print(f"  共 {len(records)} 条，开始导入...")

    conn = get_conn()
    cursor = conn.cursor()
    sql = """
        INSERT IGNORE INTO formulas
            (name, pinyin, category, ingredients, functions, analysis,
             clinical_use, pharmacology, adverse_reactions, contraindications,
             precautions, `usage`, specs, `references`)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    rows = [(
        r.get("name"),
        r.get("pinyin"),
        r.get("category"),
        r.get("ingredients"),
        r.get("functions"),
        r.get("analysis"),
        r.get("clinical_use"),
        r.get("pharmacology"),
        r.get("adverse_reactions"),
        r.get("contraindications"),
        r.get("precautions"),
        r.get("usage"),
        r.get("specs"),
        json.dumps(r.get("references", []), ensure_ascii=False),
    ) for r in records]
    count = _batch_insert(cursor, sql, rows)
    conn.commit()
    conn.close()
    return count


# ═══════════════════════════════════════════════
#  统计
# ═══════════════════════════════════════════════

def count_table(table: str) -> int:
    """查询某表记录数"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    n = cursor.fetchone()[0]
    conn.close()
    return n


# ═══════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════

def init_all() -> None:
    """一键建表 + 导入"""
    print("=" * 60)
    print("中医知识图谱 MySQL 种子数据导入")
    print(f"目标库: {settings.MYSQL_USER}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}")
    print("=" * 60)
    print()

    # 1. 建表
    create_tables()

    # 2. 导入
    print("开始导入 JSONL 数据...")
    print()

    print("[1/4] diseases")
    n = import_diseases()
    print(f"  ✓ diseases  导入 {n} 条")
    print()

    print("[2/4] syndromes")
    n = import_syndromes()
    print(f"  ✓ syndromes 导入 {n} 条")
    print()

    print("[3/4] herbs")
    n = import_herbs()
    print(f"  ✓ herbs     导入 {n} 条")
    print()

    print("[4/4] formulas")
    n = import_formulas()
    print(f"  ✓ formulas  导入 {n} 条")
    print()

    # 3. 统计验证
    print("验证 - 各表记录数:")
    print(f"  diseases  : {count_table('diseases')}")
    print(f"  syndromes : {count_table('syndromes')}")
    print(f"  herbs     : {count_table('herbs')}")
    print(f"  formulas  : {count_table('formulas')}")
    print()
    print("✓ 种子数据导入完成")


if __name__ == "__main__":
    init_all()
