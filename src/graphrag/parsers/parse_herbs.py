"""解析 2022年中药药典.txt → herbs.jsonl

纯程序解析，不使用 LLM。

文件结构（每个药材）:
  药名（中文）
  Pinyin（拼音，英文字母）
  LATIN_NAME（拉丁名，全大写）
  本品为...（来源）
  【性状】...
  【鉴别】...
  【检查】...
  【炮制】...
  【性味与归经】...
  【功能与主治】...
  【用法与用量】...
  【注意】...
  【贮藏】...

特殊行:
  缺：xxx          → 缺失的药材，跳过
  饮片              → 饮片子节标记
  附：xxx          → 附录药材

用法:
    uv run python -m src.graphrag.parsers.parse_herbs
"""

import json
import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_FILE = _PROJECT_ROOT / "src" / "graphrag" / "data" / "2022年中药药典.txt"
OUTPUT_FILE = _PROJECT_ROOT / "data" / "herbs.jsonl"

# 【字段名】正则
SECTION_RE = re.compile(r"^【(.+?)】(.*)$")
# 拼音行：以大写英文字母开头，只含字母、空格
PINYIN_RE = re.compile(r"^[A-Z][a-zA-Z\s]+$")
# 拉丁名行：全大写英文字母
LATIN_RE = re.compile(r"^[A-Z][A-Z\s]+$")
# 缺失标记
MISSING_RE = re.compile(r"^缺[：:]")


def _is_chinese_name(line: str) -> bool:
    """判断是否为药材中文名：含中文字符、不以【开头、不是拼音/拉丁"""
    if not line or line.startswith("【") or line.startswith("注"):
        return False
    if PINYIN_RE.match(line) or LATIN_RE.match(line):
        return False
    if MISSING_RE.match(line) or line.startswith("附：") or line == "饮片":
        return False
    # 含中文字符
    return bool(re.search(r"[\u4e00-\u9fff]", line))


def parse() -> list[dict]:
    with open(DATA_FILE, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f]

    entries: list[dict] = []
    i = 0
    total = len(lines)

    while i < total:
        line = lines[i].strip()

        # 跳过缺失药材
        if MISSING_RE.match(line):
            i += 1
            continue

        # 检测药材开始：中文名 + 下一行是拼音
        if _is_chinese_name(line) and i + 1 < total and PINYIN_RE.match(lines[i + 1].strip()):
            name = line.rstrip(",，")
            pinyin = lines[i + 1].strip()
            latin_name = ""
            source = ""
            sections: dict[str, str] = {}
            current_section = None
            current_text: list[str] = []
            is_appendix = False

            # 检查是否为附录
            if name.startswith("附：") or name.startswith("附:"):
                is_appendix = True
                name = name[2:].strip()

            i += 2  # 跳过名称和拼音行

            # 拉丁名（可能有也可能没有）
            if i < total and LATIN_RE.match(lines[i].strip()):
                latin_name = lines[i].strip()
                i += 1

            # 来源行（本品为...，在第一个【】之前）
            source_parts: list[str] = []
            while i < total:
                nl = lines[i].strip()
                if not nl:
                    i += 1
                    continue
                if nl.startswith("【"):
                    break
                if _is_chinese_name(nl) and i + 1 < total and PINYIN_RE.match(lines[i + 1].strip()):
                    break  # 下一个药材开始了
                if nl == "饮片":
                    i += 1
                    continue
                source_parts.append(nl)
                i += 1
            source = "".join(source_parts)

            # 解析【】字段
            while i < total:
                nl = lines[i].strip()
                if not nl:
                    i += 1
                    continue

                # 下一个药材开始？
                if _is_chinese_name(nl) and i + 1 < total and PINYIN_RE.match(lines[i + 1].strip()):
                    break
                if MISSING_RE.match(nl) and i + 1 < total and _is_chinese_name(lines[i + 1].strip()) and i + 2 < total and PINYIN_RE.match(lines[i + 2].strip()):
                    break

                m = SECTION_RE.match(nl)
                if m:
                    # 保存上一个 section
                    if current_section:
                        sections[current_section] = "".join(current_text).strip()
                    current_section = m.group(1)
                    rest = m.group(2).strip()
                    current_text = [rest] if rest else []
                elif nl == "饮片":
                    # 饮片子节，跳过标记但保留内容到当前 section
                    pass
                else:
                    if current_section:
                        current_text.append(nl)
                i += 1

            # 保存最后一个 section
            if current_section:
                sections[current_section] = "".join(current_text).strip()

            entries.append({
                "name": name,
                "pinyin": pinyin,
                "latin_name": latin_name,
                "source": source,
                "properties": sections.get("性状", ""),
                "identification": sections.get("鉴别", ""),
                "processing": sections.get("炮制", ""),
                "nature_taste_meridian": sections.get("性味与归经", sections.get("性味", "")),
                "functions": sections.get("功能与主治", sections.get("功能主治", "")),
                "usage": sections.get("用法与用量", sections.get("用法用量", "")),
                "caution": sections.get("注意", sections.get("注意事项", "")),
                "storage": sections.get("贮藏", sections.get("储藏", "")),
                "is_appendix": is_appendix,
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
    print(f"\n解析完成: 共 {len(entries)} 条药材")
    print(f"  有性味归经: {sum(1 for e in entries if e['nature_taste_meridian'])}")
    print(f"  有功能主治: {sum(1 for e in entries if e['functions'])}")
    print(f"  有用法用量: {sum(1 for e in entries if e['usage'])}")
    print(f"  附录药材: {sum(1 for e in entries if e['is_appendix'])}")

    with open(output_file, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"\n输出到: {output_file}")
    print("\n前 3 条预览:")
    for e in entries[:3]:
        print(f"  {e['name']} ({e['pinyin']}) - {e['nature_taste_meridian'][:30] if e['nature_taste_meridian'] else 'N/A'}...")


if __name__ == "__main__":
    main()
