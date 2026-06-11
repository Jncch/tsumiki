"""NG Recall を主指標とする多ラベル評価指標.

主指標: NG Recall（見逃し率の裏返し）。
補助: Precision, F-beta (beta>1, デフォルト 2)。
パターンごとの値と macro / weighted 集約を返す。

参照: docs/agent_reuse_verification_plan.md §7.1
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tsumiki.eval.labels import ClauseLabel, ClausePrediction


@dataclass(frozen=True)
class PerPatternMetric:
    pattern_id: str
    support: int  # 当該パターンが真ラベルに現れた条項数
    tp: int
    fp: int
    fn: int
    recall: float
    precision: float
    fbeta: float


@dataclass(frozen=True)
class MetricsReport:
    """評価結果. CLAUDE.md §4 の MLflow 記録に流し込む前提."""

    beta: float
    per_pattern: tuple[PerPatternMetric, ...]
    macro_recall: float
    macro_precision: float
    macro_fbeta: float
    weighted_recall: float
    weighted_precision: float
    weighted_fbeta: float
    total_support: int


def _safe_div(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


def _fbeta(precision: float, recall: float, beta: float) -> float:
    b2 = beta * beta
    den = b2 * precision + recall
    return (1 + b2) * precision * recall / den if den > 0 else 0.0


def _align(
    truth: Sequence[ClauseLabel], pred: Sequence[ClausePrediction]
) -> list[tuple[ClauseLabel, ClausePrediction]]:
    pred_by_id = {p.clause_id: p for p in pred}
    missing = [t.clause_id for t in truth if t.clause_id not in pred_by_id]
    if missing:
        raise ValueError(f"predictions missing for clause_ids: {missing[:5]} ...")
    if len(pred_by_id) != len(pred):
        raise ValueError("duplicate clause_id in predictions")
    return [(t, pred_by_id[t.clause_id]) for t in truth]


def compute_metrics(
    truth: Sequence[ClauseLabel],
    pred: Sequence[ClausePrediction],
    pattern_ids: Sequence[str],
    beta: float = 2.0,
) -> MetricsReport:
    """多ラベル分類の NG Recall / Precision / F-beta を計算する.

    pattern_ids: 評価対象とする NG パターン id の順序付き集合.
        辞書に定義された全パターンを渡すのが既定運用.
    beta: F-beta の beta. NG Recall を主指標とするため beta=2 を既定.
    """
    if beta <= 0:
        raise ValueError("beta must be positive")
    pairs = _align(truth, pred)

    per_pattern: list[PerPatternMetric] = []
    for pid in pattern_ids:
        tp = fp = fn = support = 0
        for t, p in pairs:
            in_truth = pid in t.ng_pattern_ids
            in_pred = pid in p.ng_pattern_ids
            if in_truth:
                support += 1
                if in_pred:
                    tp += 1
                else:
                    fn += 1
            else:
                if in_pred:
                    fp += 1
        recall = _safe_div(tp, tp + fn)
        precision = _safe_div(tp, tp + fp)
        fbeta = _fbeta(precision, recall, beta)
        per_pattern.append(
            PerPatternMetric(
                pattern_id=pid,
                support=support,
                tp=tp,
                fp=fp,
                fn=fn,
                recall=recall,
                precision=precision,
                fbeta=fbeta,
            )
        )

    # macro 平均は test 集合に実在するパターン（support > 0）のみで取る。
    # 出現しないパターンを recall=0 として混ぜると見かけのスコアが不当に下がる。
    nonzero = [m for m in per_pattern if m.support > 0]
    n = len(nonzero)
    macro_recall = sum(m.recall for m in nonzero) / n if n > 0 else 0.0
    macro_precision = sum(m.precision for m in nonzero) / n if n > 0 else 0.0
    macro_fbeta = sum(m.fbeta for m in nonzero) / n if n > 0 else 0.0

    total_support = sum(m.support for m in per_pattern)
    if total_support > 0:
        weighted_recall = sum(m.recall * m.support for m in per_pattern) / total_support
        weighted_precision = sum(m.precision * m.support for m in per_pattern) / total_support
        weighted_fbeta = sum(m.fbeta * m.support for m in per_pattern) / total_support
    else:
        weighted_recall = weighted_precision = weighted_fbeta = 0.0

    return MetricsReport(
        beta=beta,
        per_pattern=tuple(per_pattern),
        macro_recall=macro_recall,
        macro_precision=macro_precision,
        macro_fbeta=macro_fbeta,
        weighted_recall=weighted_recall,
        weighted_precision=weighted_precision,
        weighted_fbeta=weighted_fbeta,
        total_support=total_support,
    )
