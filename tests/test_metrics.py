"""NG Recall / Precision / F-beta 評価関数のユニットテスト."""

from __future__ import annotations

import math

import pytest

from tsumiki.eval import ClauseLabel, ClausePrediction, compute_metrics


def _label(cid: str, ngs: list[str]) -> ClauseLabel:
    return ClauseLabel(
        clause_id=cid, contract_type="nda", text="", ng_pattern_ids=frozenset(ngs)
    )


def _pred(cid: str, ngs: list[str]) -> ClausePrediction:
    return ClausePrediction(clause_id=cid, ng_pattern_ids=frozenset(ngs))


PATTERNS = ["A", "B", "C"]


def test_perfect_prediction() -> None:
    truth = [_label("c1", ["A"]), _label("c2", ["A", "B"]), _label("c3", [])]
    pred = [_pred("c1", ["A"]), _pred("c2", ["A", "B"]), _pred("c3", [])]
    rep = compute_metrics(truth, pred, PATTERNS)
    assert rep.macro_recall == 1.0
    assert rep.macro_precision == 1.0
    assert rep.macro_fbeta == 1.0
    assert rep.total_support == 3  # A:2, B:1, C:0


def test_all_missed() -> None:
    truth = [_label("c1", ["A"]), _label("c2", ["B"])]
    pred = [_pred("c1", []), _pred("c2", [])]
    rep = compute_metrics(truth, pred, PATTERNS)
    a = next(m for m in rep.per_pattern if m.pattern_id == "A")
    b = next(m for m in rep.per_pattern if m.pattern_id == "B")
    assert a.recall == 0.0
    assert a.fn == 1
    assert b.recall == 0.0
    assert rep.macro_recall == 0.0


def test_recall_dominates_fbeta_when_beta_high() -> None:
    # 真: A 1件のみ。予測: A を出すが FP も多い → precision 低、recall 高
    truth = [_label("c1", ["A"]), _label("c2", []), _label("c3", []), _label("c4", [])]
    pred = [_pred("c1", ["A"]), _pred("c2", ["A"]), _pred("c3", ["A"]), _pred("c4", [])]
    rep = compute_metrics(truth, pred, PATTERNS, beta=2.0)
    a = next(m for m in rep.per_pattern if m.pattern_id == "A")
    assert a.tp == 1
    assert a.fp == 2
    assert a.fn == 0
    assert a.recall == 1.0
    assert math.isclose(a.precision, 1 / 3)
    # F2 で recall 寄りに偏るはず
    f1 = 2 * a.precision * a.recall / (a.precision + a.recall)
    assert a.fbeta > f1


def test_align_raises_on_missing_prediction() -> None:
    truth = [_label("c1", ["A"])]
    pred: list = []
    with pytest.raises(ValueError, match="predictions missing"):
        compute_metrics(truth, pred, PATTERNS)


def test_weighted_averages_zero_support() -> None:
    truth = [_label("c1", [])]
    pred = [_pred("c1", [])]
    rep = compute_metrics(truth, pred, PATTERNS)
    assert rep.total_support == 0
    assert rep.weighted_recall == 0.0
    assert rep.weighted_precision == 0.0
    assert rep.weighted_fbeta == 0.0
