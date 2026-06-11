"""NG パターン辞書ローダーのテスト."""

from __future__ import annotations

import pytest

from tsumiki.knowledge import load_ng_patterns


def test_load_nda() -> None:
    book = load_ng_patterns("nda")
    assert book.contract_type == "nda"
    assert book.version
    assert book.last_updated
    assert len(book.patterns) >= 5
    # id 一意性
    ids = book.ids()
    assert len(ids) == len(set(ids))
    # 全パターンが必須フィールドを持つ
    for p in book.patterns:
        assert p.id and p.name and p.description
        assert p.severity in ("low", "medium", "high")


def test_by_id_missing_raises() -> None:
    book = load_ng_patterns("nda")
    with pytest.raises(KeyError):
        book.by_id("does_not_exist")


def test_nda_descriptions_have_two_stage_structure() -> None:
    """v0.2.0 以降: description に 検出すべき/紛らわしい/対象条項 の構造を含む."""
    book = load_ng_patterns("nda")
    assert book.version >= "0.2.0"
    for p in book.patterns:
        d = p.description
        assert "検出すべき" in d, f"{p.id} の description に「検出すべき」が無い"
        assert "紛らわしい" in d, f"{p.id} の description に「紛らわしい」が無い"
        assert "対象条項" in d, f"{p.id} の description に「対象条項」が無い"
