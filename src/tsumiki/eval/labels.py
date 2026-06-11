"""評価対象の条項と多ラベル NG パターンの型定義."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClauseLabel:
    """条項単位の正解ラベル.

    ng_pattern_ids が空集合の場合は「NG なし」（正常条項）を意味する。
    """

    clause_id: str
    contract_type: str
    text: str
    ng_pattern_ids: frozenset[str]


@dataclass(frozen=True)
class ClausePrediction:
    """条項単位の予測ラベル."""

    clause_id: str
    ng_pattern_ids: frozenset[str]
