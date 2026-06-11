"""T2 NG 条項修正器のテスト."""

from __future__ import annotations

import pytest

from tsumiki.baseline import (
    MODIFICATION_PROMPT_VERSION_LATEST_REUSE,
    MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE,
    build_modification_prompt,
    clean_modification_response,
    modify_clause,
)
from tsumiki.data.synthesis import ChatFn, ChatResult
from tsumiki.knowledge import load_ng_patterns


def _patterns(ids: list[str]):
    book = load_ng_patterns("nda")
    return tuple(book.by_id(i) for i in ids)


def _const_chat(content: str) -> ChatFn:
    def fn(_: str) -> ChatResult:
        return ChatResult(content=content, tokens_in=10, tokens_out=5, elapsed_ms=1.0)

    return fn


def test_reuse_prompt_includes_dictionary_for_target_only() -> None:
    """reuse 版は target_pattern_ids に該当する pattern の辞書定義を含む."""
    patterns = _patterns(["nda_scope_overbroad", "nda_duration_unbounded"])
    prompt = build_modification_prompt(
        clause_text="第1条 範囲が広い条文",
        target_pattern_ids=["nda_scope_overbroad"],
        patterns=patterns,
        prompt_version=MODIFICATION_PROMPT_VERSION_LATEST_REUSE,
    )
    assert "nda_scope_overbroad" in prompt
    # 取り除くべき NG として明示される
    assert "取り除くべき NG パターン" in prompt
    # 辞書は target に該当するもののみ展開
    assert "nda_duration_unbounded" not in prompt


def test_zerobase_prompt_omits_dictionary() -> None:
    """zerobase 版は辞書情報を一切含まない."""
    patterns = _patterns(["nda_scope_overbroad"])
    prompt = build_modification_prompt(
        clause_text="第1条 範囲が広い条文",
        target_pattern_ids=["nda_scope_overbroad"],
        patterns=patterns,
        prompt_version=MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE,
    )
    # 「不適切な部分を修正」という抽象指示のみ
    assert "不適切" in prompt
    # NG パターン id は出てこない
    assert "nda_scope_overbroad" not in prompt
    assert "NG パターン" not in prompt


def test_reuse_requires_target_ids() -> None:
    patterns = _patterns(["nda_scope_overbroad"])
    with pytest.raises(ValueError, match="target_pattern_ids is empty"):
        build_modification_prompt(
            clause_text="第1条 ...",
            target_pattern_ids=[],
            patterns=patterns,
            prompt_version=MODIFICATION_PROMPT_VERSION_LATEST_REUSE,
        )


def test_empty_clause_raises() -> None:
    patterns = _patterns(["nda_scope_overbroad"])
    with pytest.raises(ValueError, match="clause_text is empty"):
        build_modification_prompt(
            clause_text="",
            target_pattern_ids=["nda_scope_overbroad"],
            patterns=patterns,
            prompt_version=MODIFICATION_PROMPT_VERSION_LATEST_REUSE,
        )


def test_unknown_version_raises() -> None:
    patterns = _patterns(["nda_scope_overbroad"])
    with pytest.raises(ValueError, match="unsupported prompt_version"):
        build_modification_prompt(
            clause_text="第1条 ...",
            target_pattern_ids=["nda_scope_overbroad"],
            patterns=patterns,
            prompt_version="bogus.v9.9.9",
        )


def test_clean_response_strips_preamble_and_codefence() -> None:
    raw = "修正後の条項本文：\n```\n第1条 改善された条文。\n```"
    assert clean_modification_response(raw) == "第1条 改善された条文。"


def test_clean_response_keeps_inner_structure() -> None:
    raw = "第1条 ...\n1. 第1項\n2. 第2項"
    assert clean_modification_response(raw) == "第1条 ...\n1. 第1項\n2. 第2項"


def test_modify_clause_end_to_end_reuse() -> None:
    patterns = _patterns(["nda_scope_overbroad"])
    chat = _const_chat("第1条 修正された条文。")
    out = modify_clause(
        clause_text="第1条 一切の情報を秘密情報とする。",
        target_pattern_ids=["nda_scope_overbroad"],
        patterns=patterns,
        chat_fn=chat,
        prompt_version=MODIFICATION_PROMPT_VERSION_LATEST_REUSE,
    )
    assert out == "第1条 修正された条文。"


def test_modify_clause_end_to_end_zerobase() -> None:
    patterns = _patterns(["nda_scope_overbroad"])
    chat = _const_chat("第1条 修正された条文。")
    out = modify_clause(
        clause_text="第1条 一切の情報を秘密情報とする。",
        target_pattern_ids=[],  # zerobase は target を受け取らないので空でも可
        patterns=patterns,
        chat_fn=chat,
        prompt_version=MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE,
    )
    assert out == "第1条 修正された条文。"
