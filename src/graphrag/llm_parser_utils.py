"""公共工具：基于 LLM 的滑动窗口文本解析器"""

import json
import time
import dashscope
from dashscope import Generation
from src.config import settings


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """调用通义千问、返回完整响应文本。失败时自动重试。"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = Generation.call(
                model=settings.QWEN_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,          # 低温度提高稳定性
                max_tokens=4096,
                result_format="message",
            )
            if response.status_code == 200:
                return response.output.choices[0].message.content
            else:
                print(f"  LLM 调用失败 (尝试 {attempt + 1}): {response.message}")
        except Exception as e:
            print(f"  LLM 调用异常 (尝试 {attempt + 1}): {e}")
        time.sleep(2 ** attempt)
    raise RuntimeError(f"LLM 调用失败，已重试 {max_retries} 次")


def parse_with_llm(
    text_chunk: str,
    json_schema: dict,
    task_name: str,
    extra_instructions: str = "",
) -> tuple[dict | None, int]:
    """
    用 LLM 从一段文本中提取第一个实例。

    返回: (parsed_dict, cutoff_chars)
      - parsed_dict: 解析出的 JSON
      - cutoff_chars: 该实例在原 chunk 中的截止字符位置（从 0 起算）

    要求 LLM 返回格式:
    ```
    CUTOFF:1234
    { ... json ... }
    ```
    """

    system_prompt = (
        f"你是一个精确的中医药文本解析器。你的任务是：从一段可能包含多个{task_name}的"
        f"大文本中，找到「第一个完整的{task_name}」，并把它提取为给定格式的 JSON。\n\n"
        f"关键规则：\n"
        f"1. 【最重要】你的回复必须以 \"CUTOFF:N\" 作为第一行（N 是整数），"
        f"表示该条目在原文中截止到第 N 个字符（从 0 起算）。\n"
        f"2. 第二行开始是你提取出来的 JSON（必须是合法 JSON，不要加任何额外文字）。\n"
        f"3. JSON 必须严格按照给定模板的所有字段填写，值缺失则用空字符串 \"\" 或空数组 []。\n"
        f"4. 如果你无法识别任何有效条目，返回 CUTOFF:0 和空 JSON。\n"
        f"{extra_instructions}"
    )

    schema_str = json.dumps(json_schema, ensure_ascii=False, indent=2)

    user_prompt = (
        f"请从以下文本中提取第一个{task_name}：\n\n"
        f"=== 文本开始 ===\n"
        f"```\n{text_chunk}\n```\n"
        f"=== 文本结束 ===\n\n"
        f"请按照以下 JSON 模板输出：\n```json\n{schema_str}\n```\n\n"
        f"记住：第一行必须是 CUTOFF:N。"
    )

    print(f"  发送 chunk 长度={len(text_chunk)} chars ...", end=" ", flush=True)
    raw = call_llm(system_prompt, user_prompt)
    print(f"响应长度={len(raw)}")

    # 解析第一行的 CUTOFF
    cutoff = 0
    lines = raw.strip().split("\n", 1)
    if lines[0].startswith("CUTOFF:"):
        try:
            cutoff = int(lines[0].split(":", 1)[1].strip())
        except ValueError:
            print(f"  警告: 无法解析 CUTOFF 行: {lines[0]}")
    else:
        print(f"  警告: 第一行不是 CUTOFF: {lines[0][:60]}")

    # 取剩余部分作为 JSON
    json_str = lines[1].strip() if len(lines) > 1 else "{}"
    # 去掉可能的 markdown 代码块
    if json_str.startswith("```"):
        json_str = json_str.split("\n", 1)[1] if "\n" in json_str else ""
    if json_str.endswith("```"):
        json_str = json_str.rsplit("```", 1)[0]
    json_str = json_str.strip()

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"  JSON 解析失败: {e}")
        print(f"  原始 JSON: {json_str[:200]}")
        parsed = None

    return parsed, cutoff
