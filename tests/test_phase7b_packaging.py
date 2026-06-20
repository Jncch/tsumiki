"""Phase 7b: パッケージ再構成の smoke test.

設計書 `phase7_design.md` §6.2 のゲートを確認する:
  1. 新規ディレクトリの import がエラーにならない
  2. NDA `ng_patterns.yaml` と ISO27001 `audit_findings.yaml` が
     `knowledge/schemas/ng_patterns.py` の共通 schema に乗る
  3. 既存 `loader.py` 経由の import が後方互換で動く
"""

from __future__ import annotations

import importlib

import pytest

# === ゲート1: 新規ディレクトリの import smoke ===


@pytest.mark.parametrize(
    "module_name",
    [
        "tsumiki.input",
        "tsumiki.tools",
        "tsumiki.policy",
        "tsumiki.policy.compose",
        "tsumiki.policy.optimize",
        "tsumiki.policy.agentsquare",
        "tsumiki.eval.runners",
        "tsumiki.knowledge.extractors",
        "tsumiki.knowledge.schemas",
    ],
)
def test_phase7b_new_packages_importable(module_name: str) -> None:
    """設計書 §6.2 第 1 ゲート: 新規ディレクトリの import がエラーにならない."""
    mod = importlib.import_module(module_name)
    assert mod is not None


# === ゲート2: 共通 schema に NDA / ISO27001 両方が乗る ===


def _resolve_yaml_path(domain: str, filename: str) -> object:
    from importlib.resources import files

    return files("tsumiki.knowledge").joinpath(domain, filename)


def test_load_nda_yaml_via_common_schema() -> None:
    """NDA `ng_patterns.yaml` が共通 schema で読める."""
    from pathlib import Path

    from tsumiki.knowledge.schemas import load_ng_pattern_book

    path = Path(str(_resolve_yaml_path("nda", "ng_patterns.yaml")))
    book = load_ng_pattern_book(path)
    assert book.contract_type == "nda"
    assert book.domain == "nda"  # Phase 7+ alias
    assert len(book.patterns) == 9
    assert any(p.id == "nda_scope_overbroad" for p in book.patterns)
    assert len(book.topics) > 0


def test_load_iso27001_yaml_via_common_schema() -> None:
    """ISO27001 `audit_findings.yaml` が同じ共通 schema で読める."""
    from pathlib import Path

    from tsumiki.knowledge.schemas import load_ng_pattern_book

    path = Path(str(_resolve_yaml_path("iso27001", "audit_findings.yaml")))
    book = load_ng_pattern_book(path)
    assert book.contract_type == "iso27001"
    assert book.domain == "iso27001"
    assert len(book.patterns) == 9
    assert any(p.id.startswith("iso_") for p in book.patterns)
    assert len(book.topics) > 0


def test_both_domains_share_same_pattern_type() -> None:
    """NDA と ISO27001 のパターンが同一の NGPattern dataclass にロードされる.

    設計書 §6.2 第 2 ゲートの本質: schema 抽象化が成立している.
    """
    from pathlib import Path

    from tsumiki.knowledge.schemas import NGPattern, load_ng_pattern_book

    nda = load_ng_pattern_book(Path(str(_resolve_yaml_path("nda", "ng_patterns.yaml"))))
    iso = load_ng_pattern_book(
        Path(str(_resolve_yaml_path("iso27001", "audit_findings.yaml")))
    )
    for p in (*nda.patterns, *iso.patterns):
        assert isinstance(p, NGPattern)


# === ゲート3: 既存 loader.py 経由の後方互換 ===


def test_legacy_loader_reexports_nga() -> None:
    """既存 `from tsumiki.knowledge.loader import NGPattern, NGPatternBook, TopicVocab`
    が壊れていない (Phase 1〜6 の全コードがこれに依存している)."""
    from tsumiki.knowledge import loader

    assert hasattr(loader, "NGPattern")
    assert hasattr(loader, "NGPatternBook")
    assert hasattr(loader, "TopicVocab")
    assert hasattr(loader, "Topic")
    assert hasattr(loader, "load_ng_patterns")
    assert hasattr(loader, "load_ng_patterns_from_path")
    assert hasattr(loader, "load_ng_patterns_auto")


def test_legacy_load_ng_patterns_nda() -> None:
    """`load_ng_patterns('nda')` が Phase 5b 以前と同じ結果を返す."""
    from tsumiki.knowledge.loader import load_ng_patterns

    book = load_ng_patterns("nda")
    assert book.contract_type == "nda"
    assert len(book.patterns) == 9


def test_topic_vocab_is_topic_alias() -> None:
    """旧名 TopicVocab が新名 Topic の alias."""
    from tsumiki.knowledge.loader import Topic, TopicVocab

    assert Topic is TopicVocab


def test_load_ng_patterns_auto_yaml_and_dir() -> None:
    """load_ng_patterns_auto が YAML パスでも Agent Skills ディレクトリでも動く."""
    from pathlib import Path

    from tsumiki.knowledge.loader import load_ng_patterns_auto

    yaml_path = Path(str(_resolve_yaml_path("nda", "ng_patterns.yaml")))
    book_yaml = load_ng_patterns_auto(yaml_path)
    assert book_yaml.contract_type == "nda"
    assert len(book_yaml.patterns) == 9
