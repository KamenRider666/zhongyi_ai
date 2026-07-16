"""将 data/*.jsonl 中的中医知识导入 Qdrant 向量库

每一条 JSONL 记录作为一个完整、独立的文本块，不再做段落切割。

用法:
    uv run python scripts/import_to_qdrant.py                     # 导入全部 4 个文件
    uv run python scripts/import_to_qdrant.py --file herbs.jsonl  # 只导入指定文件
    uv run python scripts/import_to_qdrant.py --reset            # 先清空集合再导入
"""

import argparse
import json
import os
import sys

from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.rag.embedding import DashScopeEmbedding
from src.rag.qdrant_store import QdrantStore

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# 文件 → 分类标签
FILE_CATEGORY_MAP = {
    "herbs.jsonl": "herb",
    "formulas_test.jsonl": "formula",
    "diseases_test.jsonl": "disease",
    "syndromes_test.jsonl": "syndrome",
}


def format_herb(item: dict) -> str:
    """将一条中药记录格式化为检索友好的文本"""
    parts = []
    if item.get("name"):
        parts.append(f"【药名】{item['name']}")
    if item.get("nature_taste_meridian"):
        parts.append(f"【性味归经】{item['nature_taste_meridian']}")
    if item.get("functions"):
        parts.append(f"【功能主治】{item['functions']}")
    if item.get("usage"):
        parts.append(f"【用法用量】{item['usage']}")
    if item.get("caution"):
        parts.append(f"【注意事项】{item['caution']}")
    if item.get("source"):
        parts.append(f"【来源】{item['source']}")
    return "\n".join(parts)


def format_formula(item: dict) -> str:
    """将一条方剂记录格式化为检索友好的文本"""
    parts = []
    if item.get("name"):
        parts.append(f"【方名】{item['name']}")
    if item.get("category"):
        parts.append(f"【分类】{item['category']}")
    if item.get("ingredients"):
        parts.append(f"【组成】{item['ingredients']}")
    if item.get("functions"):
        parts.append(f"【功能主治】{item['functions']}")
    if item.get("analysis"):
        # 去掉开头的【方解】标记，避免冗余
        analysis = item["analysis"].removeprefix("【方解】").strip()
        parts.append(f"【方解】{analysis}")
    if item.get("clinical_use"):
        clinical = item["clinical_use"].removeprefix("【临床应用】").strip()
        parts.append(f"【临床应用】{clinical}")
    return "\n".join(parts)


def format_disease(item: dict) -> str:
    """将一条疾病记录格式化为检索友好的文本，跳过纯分类节点"""
    parts = []
    if item.get("name"):
        parts.append(f"【名称】{item['name']}")
    if item.get("aliases") and len(item["aliases"]) > 0:
        parts.append(f"【别名】{'、'.join(item['aliases'])}")
    if item.get("definition"):
        parts.append(f"【定义】{item['definition']}")
    if item.get("code"):
        parts.append(f"【编码】{item['code']}")
    return "\n".join(parts)


def format_syndrome(item: dict) -> str:
    """将一条证候记录格式化为检索友好的文本，跳过纯分类节点"""
    parts = []
    if item.get("name"):
        parts.append(f"【名称】{item['name']}")
    if item.get("aliases") and len(item["aliases"]) > 0:
        parts.append(f"【别名】{'、'.join(item['aliases'])}")
    if item.get("definition"):
        parts.append(f"【定义】{item['definition']}")
    if item.get("code"):
        parts.append(f"【编码】{item['code']}")
    return "\n".join(parts)


# 分类 → 格式化函数
FORMATTERS = {
    "herb": format_herb,
    "formula": format_formula,
    "disease": format_disease,
    "syndrome": format_syndrome,
}


def import_files(
    files: list[str],
    reset: bool = False,
    batch_size: int = 10,
) -> None:
    """导入指定 JSONL 文件到 Qdrant

    Args:
        files: 要导入的文件名列表（如 ["herbs.jsonl", ...]）
        reset: 是否先清空集合
        batch_size: 每批嵌入的条数
    """
    print("=" * 60)
    print("中医知识库导入 Qdrant (JSONL 模式)")
    print("=" * 60)

    from src.config import settings as s

    emb = DashScopeEmbedding(dimension=1024)
    store = QdrantStore(dim=1024)
    store.connect()

    print(f"   Qdrant:  {s.QDRANT_HOST}:{s.QDRANT_PORT}  →  {store.collection_name}")
    print(f"   Embedding: DashScope text-embedding-v3  (1024 dim)")

    # 检查/创建集合
    if reset and store.collection_exists():
        print("\n[WARN] 删除已有集合...")
        store.delete_collection()

    store.create_collection()

    # 遍历文件
    total_chunks = 0
    global_id = 0

    for filename in files:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            print(f"\n[WARN] 文件不存在，跳过: {filepath}")
            continue

        category = FILE_CATEGORY_MAP.get(filename, "unknown")
        formatter = FORMATTERS.get(category)
        print(f"\n[FILE] {filename}  (分类: {category})")

        # 读取所有行，格式化为文本块
        texts: list[str] = []
        metadata: list[dict] = []
        skipped = 0

        with open(filepath, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    print(f"   [WARN] 第{line_num}行 JSON 解析失败，跳过")
                    skipped += 1
                    continue

                # 跳过纯分类占位节点（如 diseases 中的 is_category=true）
                if item.get("is_category"):
                    skipped += 1
                    continue

                if formatter:
                    text = formatter(item)
                else:
                    # 兜底：直接把 JSON 对象转字符串
                    text = json.dumps(item, ensure_ascii=False)

                if not text.strip():
                    skipped += 1
                    continue

                texts.append(text)
                # 剔除与 payload 顶层冲突的字段（content/source/category 已单独存储）
                meta_item = {k: v for k, v in item.items()
                             if k not in ("content", "source", "category")}
                metadata.append(meta_item)

        valid = len(texts)
        print(f"   → {valid} 条有效记录" + (f"（跳过 {skipped} 条）" if skipped else ""))

        if not texts:
            continue

        # 批量嵌入 + 存储
        sources = [filename] * valid
        categories = [category] * valid

        for i in tqdm(range(0, valid, batch_size), desc="  嵌入 & 存储"):
            batch_texts = texts[i:i + batch_size]
            batch_meta = metadata[i:i + batch_size]
            batch_src = sources[i:i + batch_size]
            batch_cat = categories[i:i + batch_size]

            try:
                batch_emb = emb.encode(batch_texts)
            except Exception as e:
                print(f"\n   [ERROR] 嵌入失败 (记录 {i}-{i + len(batch_texts)}): {e}")
                continue

            store.insert(
                texts=batch_texts,
                embeddings=batch_emb,
                sources=batch_src,
                categories=batch_cat,
                id_start=global_id,
                metadata=batch_meta,
            )
            global_id += len(batch_texts)

        total_chunks += valid

    # 完成
    stats = store.get_stats()
    store.disconnect()

    print("\n" + "=" * 60)
    print(f"\n[OK] 导入完成！共 {total_chunks} 条记录存入 Qdrant")
    print(f"   统计: {stats['points']} 个向量")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导入中医知识 JSONL 到 Qdrant")
    parser.add_argument(
        "--file", type=str, default=None,
        help="指定单个文件名（默认导入全部 4 个）",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="先清空已有集合再导入",
    )
    args = parser.parse_args()

    if args.file:
        files = [args.file]
    else:
        files = list(FILE_CATEGORY_MAP.keys())

    import_files(files, reset=args.reset)
