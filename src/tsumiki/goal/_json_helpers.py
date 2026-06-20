"""LLM 応答から JSON object を取り出す共通ロジック.

parser.py / generator.py 両方から利用する.
"""

from __future__ import annotations

import json


def extract_json_object(text: str) -> dict:
    """LLM 応答テキストから JSON object 1 つを切り出してパースする.

    ``` フェンス、前後の説明文、末尾の余計な文字を吸収する.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text[3:]
        if text.startswith("json"):
            text = text[4:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found in LLM response")
    candidate = text[start:]
    end = candidate.rfind("}")
    if end < 0:
        raise ValueError("unterminated JSON object in LLM response")
    candidate = candidate[: end + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("parsed JSON is not an object")
    return parsed
