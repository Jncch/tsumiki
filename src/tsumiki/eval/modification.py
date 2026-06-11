"""Phase 2 修正成功率の評価.

T2 で生成した修正後テキストを T1 検出器に流し、
- target NG が消えたか（修正成功率）
- 元になかった NG が新規に発生していないか（負の転移率）
を測る。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ModificationOutcome:
    sample_id: str
    original_text: str
    truth_pattern_ids: frozenset[str]  # 修正前に正解として含まれていた NG
    modified_text: str
    detected_after: frozenset[str]  # 修正後に検出された NG
    target_removed: bool
    new_ng_introduced: bool


@dataclass(frozen=True)
class ModificationReport:
    n_samples: int
    n_target_removed: int
    n_new_ng_introduced: int
    modification_success_rate: float
    negative_transfer_rate: float
    # パターンごとの「修正成功率」: 各 target_pattern が消せた割合
    per_pattern_success: dict[str, float]
    per_pattern_support: dict[str, int]


def build_outcome(
    sample_id: str,
    original_text: str,
    truth_pattern_ids: frozenset[str],
    modified_text: str,
    detected_after: frozenset[str],
) -> ModificationOutcome:
    """1 サンプルの修正結果を算出.

    target_removed: truth に含まれる NG がすべて detected_after から消えている。
    new_ng_introduced: detected_after に truth に無い NG が含まれる。
    """
    target_removed = bool(truth_pattern_ids) and (truth_pattern_ids & detected_after) == frozenset()
    new_ng_introduced = bool(detected_after - truth_pattern_ids)
    return ModificationOutcome(
        sample_id=sample_id,
        original_text=original_text,
        truth_pattern_ids=truth_pattern_ids,
        modified_text=modified_text,
        detected_after=detected_after,
        target_removed=target_removed,
        new_ng_introduced=new_ng_introduced,
    )


def compute_modification_report(outcomes: Sequence[ModificationOutcome]) -> ModificationReport:
    n = len(outcomes)
    if n == 0:
        return ModificationReport(
            n_samples=0,
            n_target_removed=0,
            n_new_ng_introduced=0,
            modification_success_rate=0.0,
            negative_transfer_rate=0.0,
            per_pattern_success={},
            per_pattern_support={},
        )
    n_removed = sum(1 for o in outcomes if o.target_removed)
    n_new = sum(1 for o in outcomes if o.new_ng_introduced)

    # per-pattern: パターン p が truth に含まれた件のうち、修正後にも detected に残らなかった割合
    support: dict[str, int] = defaultdict(int)
    success: dict[str, int] = defaultdict(int)
    for o in outcomes:
        for pid in o.truth_pattern_ids:
            support[pid] += 1
            if pid not in o.detected_after:
                success[pid] += 1
    per_pattern_success = {p: success[p] / support[p] for p in support}

    return ModificationReport(
        n_samples=n,
        n_target_removed=n_removed,
        n_new_ng_introduced=n_new,
        modification_success_rate=n_removed / n,
        negative_transfer_rate=n_new / n,
        per_pattern_success=per_pattern_success,
        per_pattern_support=dict(support),
    )
