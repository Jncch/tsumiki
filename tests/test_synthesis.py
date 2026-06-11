"""合成データパイプラインのユニットテスト. LLM はモック."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tsumiki.data.clauses import CleanClause
from tsumiki.data.synthesis import (
    ChatResult,
    SynthesisConfig,
    build_injection_prompt,
    clean_response_text,
    make_sample_id,
    synthesize_sample,
    write_jsonl,
)
from tsumiki.knowledge import load_ng_patterns


def _clean() -> CleanClause:
    return CleanClause(
        clause_id="chusho_chizai_guideline:2:1",
        contract_type="nda",
        source_id="chusho_chizai_guideline",
        article_no="2-1",
        text="第2条1項 受領者は秘密情報を本目的のために必要な範囲でのみ使用する。",
    )


def _config(model: str = "qwen2.5:14b-instruct-q4_K_M") -> SynthesisConfig:
    return SynthesisConfig(model=model, seed=42, temperature=0.0)


def test_build_prompt_includes_pattern_metadata() -> None:
    book = load_ng_patterns("nda")
    patterns = (book.by_id("nda_scope_overbroad"),)
    prompt = build_injection_prompt(_clean(), patterns)
    assert "nda_scope_overbroad" in prompt
    assert "秘密情報の範囲過大" in prompt
    assert _clean().text in prompt


def test_build_prompt_requires_at_least_one_pattern() -> None:
    with pytest.raises(ValueError, match="at least one pattern"):
        build_injection_prompt(_clean(), [])


def test_clean_response_strips_preamble_and_codefence() -> None:
    raw = "以下の通りです：\n```\n第2条 改変後本文。\n```"
    assert clean_response_text(raw) == "第2条 改変後本文。"


def test_clean_response_keeps_inner_newlines() -> None:
    raw = "第1項 ...\n第2項 ..."
    assert clean_response_text(raw) == "第1項 ...\n第2項 ..."


def test_sample_id_is_deterministic() -> None:
    cfg = _config()
    id1 = make_sample_id(_clean(), ["nda_scope_overbroad"], cfg)
    id2 = make_sample_id(_clean(), ["nda_scope_overbroad"], cfg)
    assert id1 == id2
    assert id1.startswith("syn_")


def test_sample_id_distinguishes_pattern_sets() -> None:
    cfg = _config()
    id_a = make_sample_id(_clean(), ["nda_scope_overbroad"], cfg)
    id_b = make_sample_id(_clean(), ["nda_duration_unbounded"], cfg)
    assert id_a != id_b


def test_sample_id_clean_prefix_when_no_pattern() -> None:
    sid = make_sample_id(_clean(), [], _config())
    assert sid.startswith("clean_")


def test_synthesize_clean_sample_skips_llm() -> None:
    calls: list[str] = []

    def fake_chat(_: str) -> ChatResult:
        calls.append(_)
        raise AssertionError("chat_fn must not be called for clean sample")

    sample = synthesize_sample(_clean(), [], _config(), fake_chat)
    assert calls == []
    assert sample.ng_pattern_ids == ()
    assert sample.generation is None
    assert sample.text == _clean().text


def test_synthesize_injects_and_records_generation() -> None:
    book = load_ng_patterns("nda")
    patterns = (book.by_id("nda_scope_overbroad"),)

    def fake_chat(prompt: str) -> ChatResult:
        assert "nda_scope_overbroad" in prompt
        return ChatResult(
            content="第2条1項 受領者は開示された一切の情報を秘密情報とし利用できる。",
            tokens_in=120,
            tokens_out=40,
            elapsed_ms=789.0,
        )

    sample = synthesize_sample(_clean(), patterns, _config(), fake_chat)
    assert sample.ng_pattern_ids == ("nda_scope_overbroad",)
    assert "一切の情報" in sample.text
    assert sample.generation is not None
    assert sample.generation.model == "qwen2.5:14b-instruct-q4_K_M"
    assert sample.generation.tokens_in == 120
    assert sample.generation.seed == 42


def test_write_jsonl_appends(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    s1 = synthesize_sample(_clean(), [], _config(), lambda _: ChatResult("", 0, 0, 0))
    n = write_jsonl([s1], out)
    assert n == 1
    n = write_jsonl([s1], out)  # append
    assert n == 1
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    record = json.loads(lines[0])
    assert record["sample_id"].startswith("clean_")
    assert record["ng_pattern_ids"] == []
