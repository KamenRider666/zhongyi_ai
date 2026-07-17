"""解析 中医临床诊疗术语证候.txt → syndromes.jsonl

纯程序解析，不使用 LLM。
文件结构与疾病术语相同：代码层级 + 名称 + 别名 + 定义 + 注释。

用法:
    uv run python -m src.graphrag.parsers.parse_syndromes
"""

import json
import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_FILE = _PROJECT_ROOT / "src" / "graphrag" / "data" / "中医临床诊疗术语证候.txt"
OUTPUT_FILE = _PROJECT_ROOT / "data" / "syndromes.jsonl"

CODE_LINE_RE = re.compile(r"^(\d+(?:\.\d+)+)$")
SECTION_RE = re.compile(r"^(\d)([^\d.].+)$")
TRAILING_CODE_RE = re.compile(r"^(.+?。)(\d+(?:\.\d+)+)$")
NOTE_RE = re.compile(r"^(.+?)?注[：:]")


def _derive_parent_code(code: str) -> str | None:
    if "." not in code:
        return None
    return code.rsplit(".", 1)[0]


def _is_alias(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 15:
        return False
    if "。" in line or "临床" in line or "注：" in line or "注:" in line:
        return False
    if line.startswith(("因", "泛指", "指", "本", "临床", "多", "常", "可", "是", "由", "为", "以", "属", "类")):
        return False
    return True


def _is_definition(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    if line.startswith(("注：", "注:")):
        return False
    if "。" in line or len(line) > 20:
        return True
    if line.startswith(("因", "泛指", "指", "本", "临床", "多", "常", "可", "是", "由", "为", "以", "属", "类")):
        return True
    return False


def parse() -> list[dict]:
    with open(DATA_FILE, encoding="utf-8") as f:
        raw_lines = f.readlines()

    lines = [l.rstrip("\n").strip() for l in raw_lines]

    # 拆分行尾带代码的行
    processed: list[str] = []
    for line in lines:
        if not line:
            continue
        m = TRAILING_CODE_RE.match(line)
        if m and not CODE_LINE_RE.match(line) and not SECTION_RE.match(line):
            processed.append(m.group(1))
            processed.append(m.group(2))
        else:
            processed.append(line)

    # 找到第一个代码行或节标题
    start_idx = 0
    for i, line in enumerate(processed):
        if CODE_LINE_RE.match(line) or SECTION_RE.match(line):
            start_idx = i
            break
    processed = processed[start_idx:]

    entries: list[dict] = []
    i = 0
    while i < len(processed):
        line = processed[i]

        m = SECTION_RE.match(line)
        if m:
            entries.append({
                "code": m.group(1),
                "name": m.group(2).strip(),
                "aliases": [],
                "definition": "",
                "is_category": True,
                "parent_code": _derive_parent_code(m.group(1)),
            })
            i += 1
            continue

        m = CODE_LINE_RE.match(line)
        if m:
            code = m.group(1)
            i += 1
            content_lines: list[str] = []
            while i < len(processed):
                nl = processed[i]
                if CODE_LINE_RE.match(nl) or SECTION_RE.match(nl):
                    break
                if nl:
                    content_lines.append(nl)
                i += 1

            name = ""
            aliases: list[str] = []
            definition = ""

            if content_lines:
                name = content_lines[0].rstrip(",，")
                for cl in content_lines[1:]:
                    note_m = NOTE_RE.match(cl)
                    if note_m:
                        if note_m.group(1):
                            dp = note_m.group(1).strip()
                            definition = (definition + dp) if definition else dp
                    elif cl.startswith(("注：", "注:")):
                        pass
                    elif _is_definition(cl):
                        definition = (definition + cl) if definition else cl
                    elif _is_alias(cl):
                        aliases.append(cl.rstrip(",，"))
                    else:
                        definition = (definition + cl) if definition else cl

            entries.append({
                "code": code,
                "name": name,
                "aliases": aliases,
                "definition": definition,
                "is_category": False,
                "parent_code": _derive_parent_code(code),
            })
            continue

        i += 1

    # 修正 is_category
    codes_with_children = {e["parent_code"] for e in entries if e["parent_code"]}
    for e in entries:
        if e["code"] in codes_with_children:
            e["is_category"] = True

    return entries


def main():
    output_file = OUTPUT_FILE
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"输入: {DATA_FILE}")
    print(f"输出: {output_file}")

    entries = parse()
    print(f"\n解析完成: 共 {len(entries)} 条")
    print(f"  分类节点: {sum(1 for e in entries if e['is_category'])}")
    print(f"  有别名: {sum(1 for e in entries if e['aliases'])}")
    print(f"  有定义: {sum(1 for e in entries if e['definition'])}")

    with open(output_file, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"\n输出到: {output_file}")
    print("\n前 5 条预览:")
    for e in entries[:5]:
        print(f"  {e['code']} {e['name']} (parent={e['parent_code']}, cat={e['is_category']})")


if __name__ == "__main__":
    main()
