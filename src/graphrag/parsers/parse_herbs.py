"""解析 2022年中药药典 → herbs.jsonl

用法: uv run python src/graphrag/parsers/parse_herbs.py --test
   或: uv run python src/graphrag/parsers/parse_herbs.py
"""

import json

from ..llm_parser_utils import call_llm

# ============================================================
# Step 1: 分析前 100 行，确定实例最大尺寸
# ============================================================

DATA_FILE = "/src/graphrag/data/2022年中药药典.txt"
OUTPUT_FILE = "/src/graphrag/data/herbs.jsonl"

with open(DATA_FILE, encoding="utf-8") as f:
    full_text = f.read()
lines = full_text.split("\n")

print(f"文件总大小: {len(full_text)} 字符, {len(lines)} 行")
print(f"前 100 行预览 (用于确定实例最大尺寸):")
print("=" * 60)
for i, line in enumerate(lines[:100], 1):
    print(f"L{i:4d}: {line[:100]}")
print("=" * 60)

# 分析: 一个药材约 15~80 行, 每行 ~60 字符, 最大约 5000 字符
MAX_INSTANCE_CHARS = 5000
CHUNK_SIZE = int(MAX_INSTANCE_CHARS * 2.2)  # 11000

# ============================================================
# Step 2: 定义 JSON 模板
# ============================================================

HERB_TEMPLATE = {
    "name": "药材中文名",
    "pinyin": "拼音名",
    "latin_name": "拉丁名",
    "source": "基原/来源说明",
    "properties": "性状描述（长段落）",
    "identification": "鉴别方法（可能很长）",
    "processing": "炮制方法",
    "nature_taste_meridian": "性味与归经，如：辛、苦，凉。归肺、肝经。",
    "functions": "功能与主治全文",
    "usage": "用法与用量",
    "caution": "注意/禁忌（若无则为空字符串）",
    "storage": "贮藏",
    "is_appendix": False,  # 是否是附录/附属条目（如胆红素、牛胆粉）
}

# ============================================================
# Step 3: LLM 解析函数
# ============================================================

def parse_first_herb(chunk: str) -> tuple[dict | None, int]:
    """用 LLM 从 chunk 中提取第一个药材实例"""
    schema_str = json.dumps(HERB_TEMPLATE, ensure_ascii=False, indent=2)

    system = (
        "你是一个精确的中药药典文本解析器。你的任务是从一段可能包含多个药材的"
        "药典文本中，精确找到「第一个完整药材条目」，提取为指定 JSON 格式。\n\n"
        "识别规则：\n"
        "1. 每个药材条目以「药材中文名」开头（独占一行），然后是拼音名、拉丁名、来源描述。\n"
        "2. 之后可能有【性状】【鉴别】【检查】【浸出物】【含量测定】【炮制】\n"
        "   【性味与归经】【功能与主治】【用法与用量】【注意】【贮藏】等字段。\n"
        "3. 一个条目在下一条药材的中文名出现前结束，如果没有下一条就取到文本末尾。\n"
        "4. 有些条目是附属条目（如\"附：1.胆红素\"），请标记 is_appendix=true。\n"
        "5. 有些药材缺失（如\"缺：丁公藤\"），跳过它，处理下一个有实际内容的条目。\n\n"
        "输出格式：\n"
        "第一行: CUTOFF:N （N 是该条目在原文中的截止字符位置，从 0 起算）\n"
        "第二行起: 完整的 JSON, 严格按模板字段填写。"
    )

    user = (
        f"请从以下药典文本中提取第一个完整的药材条目：\n\n"
        f"=== 文本开始 ===\n```\n{chunk}\n```\n=== 文本结束 ===\n\n"
        f"JSON 模板：\n```json\n{schema_str}\n```\n\n"
        f"记住：第一行必须是 CUTOFF:N, 第二行起是 JSON。"
    )

    print(f"  请求 LLM (chunk={len(chunk)} chars)...", end=" ", flush=True)
    raw = call_llm(system, user)
    print(f"响应={len(raw)} chars")

    # 解析 CUTOFF + JSON
    header, _, body = raw.strip().partition("\n")
    cutoff = 0
    if header.startswith("CUTOFF:"):
        try:
            cutoff = int(header.split(":", 1)[1].strip())
        except ValueError:
            print(f"  警告: CUTOFF 解析失败: {header}")

    # 清洗 JSON
    body = body.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[-1] if "\n" in body else ""
    if body.endswith("```"):
        body = body.rsplit("```", 1)[0]
    body = body.strip()

    parsed = None
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as e:
        print(f"  JSON 解析失败: {e}")
        print(f"  原始内容前 200 字符: {body[:200]}")

    return parsed, cutoff


# ============================================================
# Step 4: 核心循环（test 和 main 共用）
# ============================================================

def _run(max_rounds: int | None = None):
    """核心解析循环。max_rounds=None 表示跑完全部。"""
    mode = "测试" if max_rounds else "正式"
    output_file = OUTPUT_FILE if max_rounds is None else (
        SRC_DIR.parent / "data" / "herbs_test.jsonl"
    )
    print(f"\n=== [{mode}模式] 最多 {max_rounds or '不限'} 轮 ===")
    print(f"配置: MAX_INSTANCE={MAX_INSTANCE_CHARS} chars, CHUNK_SIZE={CHUNK_SIZE} chars")
    print(f"输入: {DATA_FILE}")
    print(f"输出: {output_file}")
    print("=" * 60)

    text = full_text
    count = 0
    skipped = 0
    total_chars = len(text)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f_out:
        while text.strip():
            if max_rounds and count >= max_rounds:
                print(f"\n  达到 {max_rounds} 轮上限, 停止。")
                break

            chunk = text[:CHUNK_SIZE]

            parsed, cutoff = parse_first_herb(chunk)

            if parsed and cutoff > 0:
                name = parsed.get("name", "").strip()
                if not name or name.startswith("缺："):
                    print(f"  跳过空/缺失条目, 前进 {cutoff} chars")
                    skipped += 1
                    text = text[cutoff:]
                    continue

                f_out.write(json.dumps(parsed, ensure_ascii=False) + "\n")
                count += 1
                text = text[cutoff:]
                progress = 100 * (1 - len(text) / total_chars)
                print(f"  [{count}] {name} | cutoff={cutoff} | 剩余={len(text)} chars | 进度={progress:.1f}%")
            else:
                skip = min(500, len(text))
                print(f"  无法解析, 跳过 {skip} chars")
                text = text[skip:]

    print(f"\n{'=' * 60}")
    print(f"完成! 共解析 {count} 条药材, 跳过 {skipped} 条, 输出到 {output_file}")


def test():
    """可行性测试：只解析前 10 个实例"""
    _run(max_rounds=10)


def main():
    """正式运行：解析全部"""
    _run(max_rounds=None)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="可行性测试（只跑 10 轮）")
    args = parser.parse_args()
    test() if args.test else main()

