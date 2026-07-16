"""解析 中药成方制剂 → formulas.jsonl

用法: uv run python src/graphrag/parsers/parse_formulas.py --test
   或: uv run python src/graphrag/parsers/parse_formulas.py

注意: 成方制剂文件有大量前言（L1-L518），数据从 L519 "各论" 开始。
"""

import  json
from ..llm_parser_utils import call_llm

# ============================================================
# Step 1: 分析文件结构，定位数据起始位置，确定实例最大尺寸
# ============================================================

DATA_FILE = "/src/graphrag/data/中药成方制剂.txt"
OUTPUT_FILE = "/src/graphrag/data/formulas.jsonl"

with open(DATA_FILE, encoding="utf-8") as f:
    full_text = f.read()
lines = full_text.split("\n")

print(f"文件总大小: {len(full_text)} 字符, {len(lines)} 行")

# 查找 "各论" 的位置（真正数据开始处）
gulun_pos = full_text.find("\n各论\n")
if gulun_pos == -1:
    gulun_pos = full_text.find("各论\n")
print(f"数据起始位置 '各论': 字符偏移={gulun_pos}, 对应行号 ~{full_text[:gulun_pos].count(chr(10))}")

# 预览各论开始后的前 200 行
data_start = gulun_pos
preview = full_text[data_start:data_start + 10000]
preview_lines = preview.split("\n")
print(f"\n'各论'之后的预览 (前 100 行):")
print("=" * 60)
for i, line in enumerate(preview_lines[:100], 1):
    print(f"L{i:3d}: {line[:120]}")
print("=" * 60)

# 分析: 一个成方约 10~40 行, 每行 ~60 字符, 最大约 3000 字符
MAX_INSTANCE_CHARS = 3000
CHUNK_SIZE = int(MAX_INSTANCE_CHARS * 2.2)  # 6600

# ============================================================
# Step 2: 定义 JSON 模板
# ============================================================

FORMULA_TEMPLATE = {
    "name": "药品名称",
    "pinyin": "汉语拼音",
    "category": "分类（如 辛温解表）",
    "ingredients": "药物组成原文",
    "functions": "功能与主治原文",
    "analysis": "方解原文（包含君臣佐使分析）",
    "clinical_use": "临床应用原文",
    "pharmacology": "药理毒理原文（若无则为空字符串）",
    "adverse_reactions": "不良反应原文（若无则为空字符串）",
    "contraindications": "禁忌原文（若无则为空字符串）",
    "precautions": "注意事项原文",
    "usage": "用法与用量原文",
    "specs": "规格原文",
    "references": ["参考文献1", "参考文献2"],
}

# ============================================================
# Step 3: LLM 解析函数
# ============================================================

def parse_first_formula(chunk: str) -> tuple[dict | None, int]:
    """用 LLM 从 chunk 中提取第一个成方条目"""
    schema_str = json.dumps(FORMULA_TEMPLATE, ensure_ascii=False, indent=2)

    system = (
        "你是一个精确的中药成方制剂文本解析器。从一段中成药文本中，"
        "精确找到「第一个完整的成方条目」，提取为指定 JSON 格式。\n\n"
        "识别规则：\n"
        "1. 文本以分类标题开头（如\"内科类\\n一、解表剂\\n(一)辛温解表\"），"
        "然后是连续多个中成药条目。\n"
        "2. 每个中成药条目格式：药品名称 → 汉语拼音 → 【药物组成】【功能与主治】\n"
        "   【方解】【临床应用】【药理毒理】【不良反应】【禁忌】【注意事项】\n"
        "   【用法与用量】【规格】【参考文献】。\n"
        "3. 一个条目在下一个药品名称出现前结束。有【参考文献】的到参考文献结束。\n"
        "4. 分类标题行（如\"(一)辛温解表\"）不算作条目，跳过它们。\n"
        "5. category 字段填分类标签（如\"辛温解表\"\"清热剂\"等），从最近的分类标题提取。\n"
        "6. 所有字段尽量保留原文完整内容，不要截断。\n\n"
        "输出格式：\n"
        "第一行: CUTOFF:N （N 是该条目在原文中的截止字符位置，从 0 起算）\n"
        "第二行起: 完整的 JSON, 严格按模板字段填写。"
    )

    user = (
        f"请从以下成方制剂文本中提取第一个完整的成方条目：\n\n"
        f"=== 文本开始 ===\n```\n{chunk}\n```\n=== 文本结束 ===\n\n"
        f"JSON 模板：\n```json\n{schema_str}\n```\n\n"
        f"记住：\n"
        f"- 第一行必须是 CUTOFF:N\n"
        f"- 如果 chunk 开头就是分类标题（如\"(三)辛凉解表\"），请跳过它提取之后第一个药品\n"
        f"- 第二行起是完整 JSON"
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
        SRC_DIR.parent / "data" / "formulas_test.jsonl"
    )
    print(f"\n=== [{mode}模式] 最多 {max_rounds or '不限'} 轮 ===")
    print(f"配置: MAX_INSTANCE={MAX_INSTANCE_CHARS} chars, CHUNK_SIZE={CHUNK_SIZE} chars")
    print(f"输入: {DATA_FILE}")
    print(f"输出: {output_file}")
    print("=" * 60)

    gulun_pos = full_text.find("\n各论\n")
    if gulun_pos == -1:
        gulun_pos = full_text.find("各论\n")
    if gulun_pos == -1:
        print("错误: 找不到 '各论' 起始位置!")
        return

    text = full_text[gulun_pos + 1:]
    total_chars = len(text)

    count = 0
    skipped_categories = 0

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f_out:
        while text.strip():
            if max_rounds and count >= max_rounds:
                print(f"\n  达到 {max_rounds} 轮上限, 停止。")
                break

            chunk = text[:CHUNK_SIZE]

            parsed, cutoff = parse_first_formula(chunk)

            if parsed and cutoff > 0:
                name = parsed.get("name", "").strip()
                if not name or len(name) > 30:
                    skip = min(100, len(text))
                    print(f"  跳过分类/异常行, 前进 {skip} chars")
                    skipped_categories += 1
                    text = text[skip:]
                    continue

                f_out.write(json.dumps(parsed, ensure_ascii=False) + "\n")
                count += 1
                text = text[cutoff:]
                progress = 100 * (1 - len(text) / total_chars)
                cat = parsed.get("category", "?")
                print(f"  [{count}] [{cat}] {name} | cutoff={cutoff} | 剩余={len(text)} chars | 进度={progress:.1f}%")
            else:
                skip = min(500, len(text))
                print(f"  无法解析, 跳过 {skip} chars")
                text = text[skip:]

    print(f"\n{'=' * 60}")
    print(f"完成! 共解析 {count} 条成方, 跳过分类 {skipped_categories} 次, 输出到 {output_file}")


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

