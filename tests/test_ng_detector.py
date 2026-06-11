"""ベースライン NG 検出器のテスト. ChatFn をモックして LLM 不要."""

from __future__ import annotations

import pytest

from tsumiki.baseline import (
    build_detection_prompt,
    detect_ng_patterns,
    parse_detection_response,
    predict_clauses,
)
from tsumiki.data.clauses import CleanClause
from tsumiki.data.synthesis import ChatResult
from tsumiki.knowledge import load_ng_patterns


def _patterns(ids: list[str]):
    book = load_ng_patterns("nda")
    return tuple(book.by_id(i) for i in ids)


def _const_chat(content: str):
    def fn(_prompt: str) -> ChatResult:
        return ChatResult(content=content, tokens_in=10, tokens_out=5, elapsed_ms=1.0)

    return fn


def test_build_prompt_lists_pattern_ids() -> None:
    patterns = _patterns(["nda_scope_overbroad", "nda_duration_unbounded"])
    prompt = build_detection_prompt("第1条 範囲が広い条文。", patterns)
    assert "nda_scope_overbroad" in prompt
    assert "nda_duration_unbounded" in prompt
    assert "第1条" in prompt


def test_build_prompt_v0_2_0_mentions_absence_detection() -> None:
    """v0.2.0 は欠落型 NG の検出ヒントを含む."""
    patterns = _patterns(["nda_survival_missing"])
    prompt = build_detection_prompt("第1条", patterns, prompt_version="v0.2.0")
    assert "欠落型" in prompt
    assert "_missing" in prompt
    assert "nda_survival_missing" in prompt


def test_build_prompt_v0_1_0_still_supported() -> None:
    """旧バージョンも引き続き呼べる（比較実験用）."""
    patterns = _patterns(["nda_scope_overbroad"])
    prompt = build_detection_prompt("第1条", patterns, prompt_version="v0.1.0")
    assert "欠落型" not in prompt  # v0.1.0 にはこの語句はない
    assert "nda_scope_overbroad" in prompt


def test_build_prompt_v0_3_0_has_strict_criteria() -> None:
    """v0.3.0 は欠落型の判定条件 (a)(b)(c) と「確信を持てない場合は列挙しない」を含む."""
    patterns = _patterns(["nda_survival_missing"])
    prompt = build_detection_prompt("第1条", patterns, prompt_version="v0.3.0")
    assert "確信を持てない場合は列挙しない" in prompt
    assert "(a)" in prompt and "(b)" in prompt and "(c)" in prompt
    assert "推測解釈をしない" in prompt


def test_format_patterns_block_expands_multi_line_description() -> None:
    """ng_patterns v0.2.0 以降の複数行 description はプロンプトに全部展開される."""
    patterns = _patterns(["nda_survival_missing"])
    prompt = build_detection_prompt("第1条", patterns, prompt_version="v0.3.0")
    # 2 段構成の見出しがすべてプロンプトに含まれる
    assert "検出すべき" in prompt
    assert "紛らわしい" in prompt
    assert "対象条項" in prompt


def test_build_prompt_unknown_version_raises() -> None:
    patterns = _patterns(["nda_scope_overbroad"])
    with pytest.raises(ValueError, match="unsupported prompt_version"):
        build_detection_prompt("text", patterns, prompt_version="v9.9.9")


def test_build_prompt_rejects_empty_patterns() -> None:
    with pytest.raises(ValueError, match="at least one pattern"):
        build_detection_prompt("text", [])


def test_parse_simple_lines() -> None:
    valid = {"a", "b", "c"}
    assert parse_detection_response("a\nb", valid) == frozenset({"a", "b"})


def test_parse_strips_bullets_and_numbers() -> None:
    valid = {"nda_scope_overbroad", "nda_duration_unbounded"}
    raw = "- nda_scope_overbroad\n1. nda_duration_unbounded\n* unknown_id"
    assert parse_detection_response(raw, valid) == frozenset(
        {"nda_scope_overbroad", "nda_duration_unbounded"}
    )


def test_parse_filters_hallucinated_ids() -> None:
    valid = {"a"}
    raw = "a\nz\n"
    assert parse_detection_response(raw, valid) == frozenset({"a"})


def test_parse_handles_comma_separated() -> None:
    valid = {"a", "b"}
    assert parse_detection_response("a, b、unknown", valid) == frozenset({"a", "b"})


def test_parse_empty_returns_empty() -> None:
    assert parse_detection_response("", {"a"}) == frozenset()
    assert parse_detection_response("\n\n", {"a"}) == frozenset()


def test_detect_ng_patterns_end_to_end() -> None:
    patterns = _patterns(["nda_scope_overbroad", "nda_duration_unbounded"])
    chat = _const_chat("nda_scope_overbroad")
    result = detect_ng_patterns("どんな条項でも", patterns, chat)
    assert result == frozenset({"nda_scope_overbroad"})


def test_predict_clauses_returns_predictions_aligned_to_clauses() -> None:
    patterns = _patterns(["nda_scope_overbroad"])
    clauses = [
        CleanClause(
            clause_id="c1",
            contract_type="nda",
            source_id="s",
            article_no="1",
            text="第1条 a",
        ),
        CleanClause(
            clause_id="c2",
            contract_type="nda",
            source_id="s",
            article_no="2",
            text="第2条 b",
        ),
    ]
    chat = _const_chat("nda_scope_overbroad")
    preds = predict_clauses(clauses, patterns, chat)
    assert [p.clause_id for p in preds] == ["c1", "c2"]
    assert all(p.ng_pattern_ids == frozenset({"nda_scope_overbroad"}) for p in preds)


# --- v0.5.0 (P5-A: topic matching) ---


def test_build_prompt_v0_5_0_requires_topics() -> None:
    """v0.5.0 は topics を必須とする."""
    patterns = _patterns(["nda_scope_overbroad"])
    with pytest.raises(ValueError, match="v0.5.0 requires non-empty topics"):
        build_detection_prompt("第1条", patterns, prompt_version="v0.5.0")


def test_build_prompt_v0_5_0_includes_topics_and_applicable_topics() -> None:
    """v0.5.0 はトピック語彙と各パターンの applicable_topics を含む."""
    book = load_ng_patterns("nda")
    patterns = (book.by_id("nda_jurisdiction_one_sided"),)
    prompt = build_detection_prompt(
        "第1条 紛争解決",
        patterns,
        prompt_version="v0.5.0",
        topics=book.topics,
    )
    # 主題語彙が列挙されている
    assert "jurisdiction" in prompt
    assert "紛争解決" in prompt
    # applicable_topics 行が含まれる
    assert "applicable_topics:" in prompt
    # 手順の指示
    assert "ステップ 1" in prompt
    assert "applicable_topics に含まれないパターンは" in prompt


def test_parse_v0_5_0_ignores_topic_line() -> None:
    """v0.5.0 の応答先頭の `topic: <id>` 行は無視され NG id のみ拾われる."""
    valid = {"nda_scope_overbroad", "nda_duration_unbounded"}
    raw = "topic: definition\nnda_scope_overbroad\n"
    assert parse_detection_response(raw, valid) == frozenset({"nda_scope_overbroad"})


def test_parse_v0_5_0_topic_only_returns_empty() -> None:
    """topic: 行のみ（該当 NG なし）なら空集合."""
    valid = {"nda_scope_overbroad"}
    assert parse_detection_response("topic: other\n", valid) == frozenset()


def test_load_ng_patterns_v0_3_0_has_topics_and_applicable_topics() -> None:
    """ng_patterns v0.3.0 が topics と applicable_topics を持つ."""
    book = load_ng_patterns("nda")
    assert book.version == "0.3.0"
    assert len(book.topics) > 0
    assert {"definition", "secrecy", "jurisdiction", "liability"} <= set(book.topic_ids())
    for p in book.patterns:
        assert p.applicable_topics, f"{p.id} has no applicable_topics"


def test_build_prompt_v0_5_0_rejects_patterns_without_applicable_topics() -> None:
    """v0.5.0 は applicable_topics 空のパターンを拒否する."""
    from tsumiki.knowledge.loader import NGPattern, TopicVocab

    p_bad = NGPattern(
        id="x_bad", name="X", description="d", severity="low", applicable_topics=()
    )
    with pytest.raises(ValueError, match="applicable_topics"):
        build_detection_prompt(
            "第1条",
            [p_bad],
            prompt_version="v0.5.0",
            topics=(TopicVocab(id="t1", name="T1"),),
        )
