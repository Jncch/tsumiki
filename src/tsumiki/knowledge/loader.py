"""NG パターン辞書のローダー.

Phase 7b で dataclass と YAML パースを `knowledge/schemas/ng_patterns.py`
に集約した. 本モジュールは既存 import (NGPattern / NGPatternBook /
TopicVocab / load_ng_patterns / load_ng_patterns_from_path /
load_ng_patterns_auto) を破壊変更しないための後方互換層.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from tsumiki.knowledge.schemas.ng_patterns import (
    NGPattern,
    NGPatternBook,
    Severity,
    Topic,
    _coerce_severity,  # noqa: F401  # skills_loader.py から後方互換 import される
    _parse_topics,  # noqa: F401  # 同上
    load_ng_pattern_book,
    parse_doc,
)

# Phase 5 以前の旧名. 新規コードは Topic を使う.
TopicVocab = Topic

__all__ = [
    "NGPattern",
    "NGPatternBook",
    "Severity",
    "Topic",
    "TopicVocab",
    "load_ng_patterns",
    "load_ng_patterns_from_path",
    "load_ng_patterns_auto",
]


def load_ng_patterns(contract_type: str = "nda") -> NGPatternBook:
    """同梱の知識資産から NG パターン辞書をロードする.

    contract_type に対応する `src/tsumiki/knowledge/<contract_type>/ng_patterns.yaml`
    を読む. (歴史的経緯でファイル名が固定. ISO27001 は audit_findings.yaml の
    ため本関数では扱えない. その場合は load_ng_patterns_from_path / _auto を使う.)
    """
    resource = files("tsumiki.knowledge").joinpath(contract_type, "ng_patterns.yaml")
    import yaml

    text = resource.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise ValueError(f"yaml root must be a mapping, got {type(doc).__name__}")
    return parse_doc(doc)


def load_ng_patterns_from_path(path: Path) -> NGPatternBook:
    """任意パスから NG パターン辞書をロードする (実験用)."""
    return load_ng_pattern_book(path)


def load_ng_patterns_auto(path: Path) -> NGPatternBook:
    """パスがファイルなら YAML, ディレクトリなら Agent Skills 形式を自動判別する.

    Phase 5b で導入. Phase 5c の `runner/e2e.py` が両形式を扱えるようにする入口.
    """
    if path.is_dir():
        from tsumiki.knowledge.skills_loader import load_skills_dir

        return load_skills_dir(path)
    return load_ng_pattern_book(path)
