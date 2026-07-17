"""解析 中药成方制剂.txt → formulas.jsonl

纯程序解析，不使用 LLM。

文件结构:
  - 前言（L1-L518，跳过）
  - "各论" 标记（L520）
  - 科系分类：内科类、外科类 等
  - 功效分类：一、解表剂 等（含概述段落）
  - 细分类：(一)辛温解表 等
  - 方剂条目：
    方名（中文）
    Pinyin（拼音，可能跨多行）
    【药物组成】...
    【功能与主治】...
    【方解】...
    【临床应用】...
    【药理毒理】...
    【不良反应】...
    【禁忌】...
    【注意事项】...
    【用法与用量】...
    【规格】...
    【参考文献】...

用法:
    uv run python -m src.graphrag.parsers.parse_formulas
"""

import json
import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_FILE = _PROJECT_ROOT / "src" / "graphrag" / "data" / "中药成方制剂.txt"
OUTPUT_FILE = _PROJECT_ROOT / "data" / "formulas.jsonl"

SECTION_RE = re.compile(r"^【(.+?)】(.*)$")
# 拼音行：以大写英文字母开头
PINYIN_RE = re.compile(r"^[A-Z][a-zA-Z]")
# 大分类标题：一、解表剂 / 二、清热剂
CATEGORY_HEADER_RE = re.compile(r"^[一二三四五六七八九十]+[、.](.+)")
# 细分类标题：(一)辛温解表 / (二)辛凉解表
SUBCATEGORY_RE = re.compile(r"^\([一二三四五六七八九十]+\)(.+)")


def _is_formula_name(line: str) -> bool:
    """判断是否为方剂名：中文、不含数字编号、不以【开头"""
    if not line or line.startswith("【") or line.startswith("注"):
        return False
    if CATEGORY_HEADER_RE.match(line):
        return False
    if line.endswith("类") or line.endswith("剂"):
        return False
    # 纯英文/拼音行不是方名
    if PINYIN_RE.match(line):
        return False
    # 含中文字符且不太长（方名一般 2-30 字符）
    if re.search(r"[\u4e00-\u9fff]", line) and len(line) <= 50:
        return True
    return False


def _is_pinyin_line(line: str) -> bool:
    """是否为拼音行"""
    return bool(PINYIN_RE.match(line))


def parse() -> list[dict]:
    with open(DATA_FILE, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f]

    # 找到 "各论" 位置，跳过前言
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip() == "各论":
            start_idx = i + 1
            break

    lines = lines[start_idx:]
    total = len(lines)
    entries: list[dict] = []
    i = 0
    current_category = ""  # 跟踪当前细分类（如"辛温解表"）

    while i < total:
        line = lines[i].strip()

        # 跟踪细分类标题：(一)辛温解表
        sub_m = SUBCATEGORY_RE.match(line)
        if sub_m:
            current_category = sub_m.group(1).strip()
            i += 1
            continue

        # 跟踪大分类标题：一、解表剂
        cat_m = CATEGORY_HEADER_RE.match(line)
        if cat_m:
            # 大分类作为兜底（细分类更精确，优先用细分类）
            if not current_category:
                current_category = cat_m.group(1).strip()
            i += 1
            continue

        # 科系大类（内科类、外科类等）重置细分类
        if line.endswith("类") and len(line) <= 10:
            current_category = ""
            i += 1
            continue

        # 检测方剂开始：方名 + 下一行是拼音
        if _is_formula_name(line) and i + 1 < total and _is_pinyin_line(lines[i + 1].strip()):
            name = line
            # 收集拼音（可能跨多行）
            pinyin_parts: list[str] = []
            i += 1
            while i < total:
                nl = lines[i].strip()
                if not nl:
                    i += 1
                    break
                if _is_pinyin_line(nl):
                    pinyin_parts.append(nl)
                    i += 1
                elif nl.startswith("【"):
                    break
                else:
                    # 非拼音非【】行，可能是拼音的续行或方名的补充
                    if pinyin_parts:
                        pinyin_parts.append(nl)
                        i += 1
                    else:
                        break
            pinyin = " ".join(pinyin_parts)

            # 解析【】字段
            sections: dict[str, str] = {}
            current_section = None
            current_text: list[str] = []

            while i < total:
                nl = lines[i].strip()
                if not nl:
                    i += 1
                    continue

                # 下一个方剂开始？
                if _is_formula_name(nl) and i + 1 < total and _is_pinyin_line(lines[i + 1].strip()):
                    break

                m = SECTION_RE.match(nl)
                if m:
                    if current_section:
                        sections[current_section] = "".join(current_text).strip()
                    current_section = m.group(1)
                    rest = m.group(2).strip()
                    current_text = [rest] if rest else []
                else:
                    if current_section:
                        current_text.append(nl)
                    # 没有 current_section 的行（分类描述等）跳过
                i += 1

            # 保存最后一个 section
            if current_section:
                sections[current_section] = "".join(current_text).strip()

            # 解析参考文献为列表
            refs_text = sections.get("参考文献", "")
            references = []
            if refs_text:
                # 按 [1] [2] 或序号拆分
                ref_parts = re.split(r"\[\d+\]", refs_text)
                references = [p.strip() for p in ref_parts if p.strip()]

            entries.append({
                "name": name,
                "pinyin": pinyin,
                "category": current_category,
                "ingredients": sections.get("药物组成", ""),
                "functions": sections.get("功能与主治", sections.get("功能主治", "")),
                "analysis": sections.get("方解", ""),
                "clinical_use": sections.get("临床应用", ""),
                "pharmacology": sections.get("药理毒理", ""),
                "adverse_reactions": sections.get("不良反应", ""),
                "contraindications": sections.get("禁忌", ""),
                "precautions": sections.get("注意事项", ""),
                "usage": sections.get("用法与用量", sections.get("用法用量", "")),
                "specs": sections.get("规格", ""),
                "references": references,
            })
            continue

        i += 1

    return entries


def main():
    output_file = OUTPUT_FILE
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"输入: {DATA_FILE}")
    print(f"输出: {output_file}")

    entries = parse()
    print(f"\n解析完成: 共 {len(entries)} 条方剂")
    print(f"  有分类: {sum(1 for e in entries if e['category'])}")
    print(f"  有药物组成: {sum(1 for e in entries if e['ingredients'])}")
    print(f"  有功能主治: {sum(1 for e in entries if e['functions'])}")
    print(f"  有方解: {sum(1 for e in entries if e['analysis'])}")
    print(f"  有临床应用: {sum(1 for e in entries if e['clinical_use'])}")

    # 分类统计
    cats = {}
    for e in entries:
        c = e["category"]
        if c:
            cats[c] = cats.get(c, 0) + 1
    if cats:
        print(f"\n  分类分布 (前 10):")
        for c, n in sorted(cats.items(), key=lambda x: -x[1])[:10]:
            print(f"    {c}: {n}")

    with open(output_file, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"\n输出到: {output_file}")
    print("\n前 3 条预览:")
    for e in entries[:3]:
        print(f"  {e['name']} ({e['pinyin']}) - 组成: {e['ingredients'][:40] if e['ingredients'] else 'N/A'}...")


if __name__ == "__main__":
    main()
