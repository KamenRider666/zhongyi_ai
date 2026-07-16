"""解析 中医临床诊疗术语疾病 → diseases.jsonl

用法: uv run python src/graphrag/parsers/parse_diseases.py --test
   或: uv run python src/graphrag/parsers/parse_diseases.py
"""

import json

from ..llm_parser_utils import call_llm

# ============================================================
# Step 1: 分析前 100 行，确定实例最大尺寸
# ============================================================

DATA_FILE = "/src/graphrag/data/中医临床诊疗术语疾病.txt"
OUTPUT_FILE = "/src/graphrag/data/diseases.jsonl"

with open(DATA_FILE, encoding="utf-8") as f:
    full_text = f.read()
lines = full_text.split("\n")

print(f"文件总大小: {len(full_text)} 字符, {len(lines)} 行")
print(f"前 100 行预览 (用于确定实例最大尺寸):")
print("=" * 60)
for i, line in enumerate(lines[:100], 1):
    print(f"L{i:4d}: {line[:120]}")
print("=" * 60)

# 分析: 一个疾病条目约 3~15 行, 每行 ~60 字符, 最大约 800 字符
MAX_INSTANCE_CHARS = 800
CHUNK_SIZE = int(MAX_INSTANCE_CHARS * 2.2)  # 1760

# ============================================================
# Step 2: 定义 JSON 模板
# ============================================================

DISEASE_TEMPLATE = {
    "code": "编号如 3.1.1.1",
    "name": "疾病名称",
    "aliases": ["别名1", "别名2"],
    "definition": "完整定义/描述文本",
    "is_category": False,  # 是否只是类目词（如"泛指...一类外感病"）
    "parent_code": "父级编号（如 3.1.1 → 3.1），若无则 null",
}

# ============================================================
# Step 3: LLM 解析函数
# ============================================================

def parse_first_disease(chunk: str) -> tuple[dict | None, int]:
    """用 LLM 从 chunk 中提取第一个疾病条目"""
    schema_str = json.dumps(DISEASE_TEMPLATE, ensure_ascii=False, indent=2)

    system = (
        "你是一个精确的中医疾病术语文本解析器。从一段包含多个疾病条目的文本中，"
        "精确找到「第一个完整的疾病条目」，提取为指定 JSON 格式。\n\n"
        "识别规则：\n"
        "1. 文本格式：首先是文件前言（前几行），然后是编号条目。\n"
        "2. 每个条目以编号开头（如 \"3.1\\n\"），然后是一行或多行名称，然后是定义文本。\n"
        "3. 如果名称后面有 \"注：...\" 则是注解，应包含在 definition 中但不要作为新条目。\n"
        "4. 有些是纯类目词（如\"泛指...一类...\"）, 标记 is_category=true。\n"
        "5. 别名从名称行后的行提取（编号行之后、定义行之前）。\n"
        "6. 层级关系从编号推导：3.1.1 的 parent 是 3.1, 3.1 的 parent 是 null。\n\n"
        "输出格式：\n"
        "第一行: CUTOFF:N （N 是该条目在原文中的截止字符位置，从 0 起算）\n"
        "第二行起: 完整的 JSON, 严格按模板字段填写。"
    )

    user = (
        f"请从以下文本中提取第一个完整的疾病条目：\n\n"
        f"=== 文本开始 ===\n```\n{chunk}\n```\n=== 文本结束 ===\n\n"
        f"JSON 模板：\n```json\n{schema_str}\n```\n\n"
        f"记住：第一行必须是 CUTOFF:N, 第二行起是 JSON。"
    )

    print(f"  请求 LLM (chunk={len(chunk)} chars)...", end=" ", flush=True)
    raw = call_llm(system, user)
    print(f"响应={len(raw)} chars")

    header, _, body = raw.strip().partition("\n")
    cutoff = 0
    if header.startswith("CUTOFF:"):
        try:
            cutoff = int(header.split(":", 1)[1].strip())
        except ValueError:
            print(f"  警告: CUTOFF 解析失败: {header}")

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
        SRC_DIR.parent / "data" / "diseases_test.jsonl"
    )
    print(f"\n=== [{mode}模式] 最多 {max_rounds or '不限'} 轮 ===")
    print(f"配置: MAX_INSTANCE={MAX_INSTANCE_CHARS} chars, CHUNK_SIZE={CHUNK_SIZE} chars")
    print(f"输入: {DATA_FILE}")
    print(f"输出: {output_file}")
    print("=" * 60)

    text = full_text
    text = text.split("\n", 2)[-1] if text.startswith("中医临床诊疗术语") else text

    count = 0
    total_chars = len(text)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f_out:
        while text.strip():
            if max_rounds and count >= max_rounds:
                print(f"\n  达到 {max_rounds} 轮上限, 停止。")
                break

            chunk = text[:CHUNK_SIZE]

            parsed, cutoff = parse_first_disease(chunk)

            if parsed and cutoff > 0:
                f_out.write(json.dumps(parsed, ensure_ascii=False) + "\n")
                count += 1
                text = text[cutoff:]
                progress = 100 * (1 - len(text) / total_chars)
                name = parsed.get("name", "?")
                code = parsed.get("code", "?")
                print(f"  [{count}] {code} {name} | cutoff={cutoff} | 剩余={len(text)} chars | 进度={progress:.1f}%")
            else:
                skip = min(200, len(text))
                print(f"  无法解析, 跳过 {skip} chars")
                text = text[skip:]

    print(f"\n{'=' * 60}")
    print(f"完成! 共解析 {count} 条疾病, 输出到 {output_file}")


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

