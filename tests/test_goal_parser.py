"""goal/parser.py のテスト. LLM 応答をスタブ化して TaskSpec への変換を検証."""

from __future__ import annotations

import json

import pytest

from tsumiki.goal.parser import build_parse_prompt, parse_goal


_NDA_RESPONSE = json.dumps(
    {
        "task_class": "detect_and_modify",
        "domain": "nda",
        "input_roles": [
            {
                "name": "target_document",
                "formats": ["pdf", "docx", "md"],
                "role": "target",
                "description": "チェック対象の NDA 本文",
            }
        ],
        "knowledge": {
            "source_type": "existing",
            "catalog_path": "knowledge/skills/nda/ng_patterns/",
            "extraction_hints": [],
        },
        "outputs": [
            {
                "name": "findings",
                "schema_id": "ng_findings_v1",
                "description": "NG 条項リスト",
            },
            {
                "name": "modified_document",
                "schema_id": "modified_text_v1",
                "description": "修正後の本文",
            },
        ],
        "evaluator_hints": [
            "target_pattern が修正後に残らない率",
            "target 以外の NG が新規発生する率も測る",
        ],
    },
    ensure_ascii=False,
)


def test_parse_goal_basic() -> None:
    spec = parse_goal("NDA をレビューして NG 条項を直したい", lambda _: _NDA_RESPONSE)
    assert spec.task_class == "detect_and_modify"
    assert spec.domain == "nda"
    assert len(spec.input_roles) == 1
    assert spec.input_roles[0].name == "target_document"
    assert spec.input_roles[0].role == "target"
    assert spec.knowledge.source_type == "existing"
    assert spec.knowledge.catalog_path == "knowledge/skills/nda/ng_patterns/"
    assert len(spec.outputs) == 2
    assert spec.outputs[0].schema_id == "ng_findings_v1"
    assert spec.raw_goal == "NDA をレビューして NG 条項を直したい"


def test_parse_goal_handles_code_fence() -> None:
    """LLM が ```json ... ``` でラップする場合の対応."""
    text = "```json\n" + _NDA_RESPONSE + "\n```"
    spec = parse_goal("foo", lambda _: text)
    assert spec.task_class == "detect_and_modify"


def test_parse_goal_handles_preamble_text() -> None:
    """LLM が余計な前置きを出力する場合も先頭の { を見つけてパースする."""
    text = "以下の構造で解釈しました.\n" + _NDA_RESPONSE
    spec = parse_goal("foo", lambda _: text)
    assert spec.domain == "nda"


def test_parse_goal_missing_json_raises() -> None:
    with pytest.raises(ValueError, match="no JSON object found"):
        parse_goal("foo", lambda _: "JSON 出力できませんでした")


def test_build_parse_prompt_unknown_version() -> None:
    with pytest.raises(ValueError, match="unsupported prompt_version"):
        build_parse_prompt("foo", prompt_version="v9.9")


def test_build_parse_prompt_includes_goal() -> None:
    prompt = build_parse_prompt("テスト目的")
    assert "テスト目的" in prompt
    assert "task_class" in prompt
    assert "input_roles" in prompt


def test_three_paraphrases_normalize_to_same_signature() -> None:
    """Phase 5c §3.2 ゲート: 3 種の自然言語入力が同一 TaskSpec に正規化される.

    LLM 応答を「同じ JSON を返す」というスタブで模倣することで、
    parser 側のロジック (生成 JSON → TaskSpec) が異なる goal でも同じ
    シグネチャを返すことだけを検証する.
    """
    goals = [
        "NDA をレビューしたい",
        "NG 条項を検出して直したい",
        "秘密保持契約のチェック",
    ]
    specs = [parse_goal(g, lambda _: _NDA_RESPONSE) for g in goals]
    sigs = {s.io_signature() for s in specs}
    assert len(sigs) == 1
    assert all(s.task_class == "detect_and_modify" for s in specs)
    assert all(s.domain == "nda" for s in specs)
