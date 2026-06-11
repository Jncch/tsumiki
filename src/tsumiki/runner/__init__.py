"""End-to-end の実験 Runner.

Phase 1: 合成データ生成 → 層化分割 → ベースライン予測 → 評価 → MLflow 記録.
Phase 2: 再利用 vs ゼロベースの修正対照実験 → MLflow 記録.
"""

from tsumiki.runner.phase1 import (
    Phase1Outcome,
    build_labeled_samples,
    evaluate_baseline,
    run_phase1,
)
from tsumiki.runner.phase2 import (
    Phase2Outcome,
    run_phase2_variant,
)

__all__ = [
    "Phase1Outcome",
    "Phase2Outcome",
    "build_labeled_samples",
    "evaluate_baseline",
    "run_phase1",
    "run_phase2_variant",
]
