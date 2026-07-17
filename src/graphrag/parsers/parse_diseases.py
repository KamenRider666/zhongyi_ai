"""解析 中医临床诊疗术语疾病.txt → diseases.jsonl

纯程序解析，不使用 LLM（文件结构规整，可确定性解析）。

文件结构:
  - 文件头：前言/说明（跳过）
  - 节标题：如 "3外感病类术语"（代码+名称同行，代码为单个数字）
  - 词条：代码独占一行（如 3.1、3.1.1.1），后续行为名称、别名、定义、注释

parent_code 推导（去掉最后一段 .x）:
  3.1.1.1 → 3.1.1
  3.1.1   → 3.1
  3.1     → 3
  3       → null

用法:
    uv run python -m src.graphrag.parsers.parse_diseases
"""

import json
import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_FILE = _PROJECT_ROOT / "src" / "graphrag" / "data" / "中医临床诊疗术语疾病.txt"
OUTPUT_FILE = _PROJECT_ROOT / "data" / "diseases.jsonl"

# 代码行正则：纯数字+点，如 3.1、3.1.1.1、14.1
CODE_LINE_RE = re.compile(r"^(\d+(?:\.\d+)+)$")
# 节标题正则：单个数字开头紧跟中文，如 3外感病类术语
SECTION_RE = re.compile(r"^(\d)([^\d.].+)$")
# 行尾代码：如 "...为特征的痹病。9.6.12"
TRAILING_CODE_RE = re.compile(r"^(.+?。)(\d+(?:\.\d+)+)$")
# 注释行
NOTE_RE = re.compile(r"^(.+?)?注[：:]")


def _derive_parent_code(code: str) -> str | None:
    """从代码推导父级代码：3.1.1 → 3.1，3.1 → 3，3 → null"""
    if "." not in code:
        return None
    return code.rsplit(".", 1)[0]


def _is_alias(line: str) -> bool:
    """判断一行是否为别名（短、无句号、不像定义）"""
    line = line.strip()
    if not line or len(line) > 15:
        return False
    if "。" in line or "临床" in line or "注：" in line or "注:" in line:
        return False
    if line.startswith(("因", "泛指", "指", "本", "临床", "多", "常", "可", "是", "由", "为", "以", "属", "类")):
        return False
    return True


def _is_definition(line: str) -> bool:
    """判断一行是否为定义"""
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
    """解析整个文件，返回词条列表"""
    with open(DATA_FILE, encoding="utf-8") as f:
        raw_lines = f.readlines()

    # 预处理：找到第一个节标题，跳过文件头
    start_idx = 0
    for i, line in enumerate(raw_lines):
        if SECTION_RE.match(line.strip()):
            start_idx = i
            break

    lines = [l.rstrip("\n").strip() for l in raw_lines[start_idx:]]

    # 进一步预处理：拆分行尾带代码的行
    # 如 "...为特征的痹病。9.6.12" → ["...为特征的痹病。", "9.6.12"]
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

    # 解析词条
    entries: list[dict] = []
    i = 0
    while i < len(processed):
        line = processed[i]

        # 节标题：如 "3外感病类术语"
        m = SECTION_RE.match(line)
        if m:
            code = m.group(1)
            name = m.group(2).strip()
            entries.append({
                "code": code,
                "name": name,
                "aliases": [],
                "definition": "",
                "is_category": True,  # 先标记，后面根据子节点修正
                "parent_code": _derive_parent_code(code),
            })
            i += 1
            continue

        # 代码行：如 "3.1.1"
        m = CODE_LINE_RE.match(line)
        if m:
            code = m.group(1)
            i += 1

            # 收集该词条的所有内容行
            content_lines: list[str] = []
            while i < len(processed):
                next_line = processed[i]
                if CODE_LINE_RE.match(next_line) or SECTION_RE.match(next_line):
                    break
                if next_line:
                    content_lines.append(next_line)
                i += 1

            # 解析内容行：第一行是名称，后续是别名/定义/注释
            name = ""
            aliases: list[str] = []
            definition = ""
            notes: list[str] = []

            if content_lines:
                name = content_lines[0].rstrip(",，")

                for cl in content_lines[1:]:
                    # 拆分嵌入的注释（如 "...一类外感病。注：包括..."）
                    note_m = NOTE_RE.match(cl)
                    if note_m:
                        if note_m.group(1):
                            # 注释前有定义内容
                            def_part = note_m.group(1).strip()
                            if def_part and not definition:
                                definition = def_part
                            elif def_part:
                                definition += def_part
                        note_text = cl[cl.index("注"):].strip()
                        notes.append(note_text)
                    elif cl.startswith(("注：", "注:")):
                        notes.append(cl)
                    elif _is_definition(cl):
                        if definition:
                            definition += cl
                        else:
                            definition = cl
                    elif _is_alias(cl):
                        aliases.append(cl.rstrip(",，"))
                    else:
                        # 兜底：当作定义的一部分
                        if definition:
                            definition += cl
                        else:
                            definition = cl

            entries.append({
                "code": code,
                "name": name,
                "aliases": aliases,
                "definition": definition,
                "is_category": False,  # 先标记 false，后面根据子节点修正
                "parent_code": _derive_parent_code(code),
            })
            continue

        i += 1

    # 修正 is_category：有子节点的标记为 True
    codes_with_children = set()
    for e in entries:
        pc = e["parent_code"]
        if pc:
            codes_with_children.add(pc)
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

    # 统计
    categories = sum(1 for e in entries if e["is_category"])
    with_aliases = sum(1 for e in entries if e["aliases"])
    with_definition = sum(1 for e in entries if e["definition"])
    print(f"  分类节点: {categories}")
    print(f"  有别名: {with_aliases}")
    print(f"  有定义: {with_definition}")

    # 层级统计
    max_depth = max(e["code"].count(".") for e in entries)
    print(f"  最大层级深度: {max_depth + 1}")

    with open(output_file, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"\n输出到: {output_file}")

    # 抽查前 5 条
    print("\n前 5 条预览:")
    for e in entries[:5]:
        print(f"  {e['code']} {e['name']} (parent={e['parent_code']}, category={e['is_category']})")


if __name__ == "__main__":
    main()
