"""NDA 用初期評価器を eval/generated/nda/detect_and_modify/<id>/ に保存する.

Phase 1〜4 で実装した tsumiki.eval.modification.compute_modification_report を
Q3=B 決定関数として Agent Skills 流用蓄積の形式に移植する.

設計: docs/experiments/phase5c_design.md §1.4
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tsumiki.goal import EvaluatorSpec, TestCase
from tsumiki.goal.store import save

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = PROJECT_ROOT / "src" / "tsumiki" / "eval" / "generated"

EVALUATOR_CODE = '''"""NDA detect_and_modify 用評価器.

Phase 1〜4 で実装した tsumiki.eval.modification.compute_modification_report の移植版.
流用蓄積から動的ロードして使う.
"""

from __future__ import annotations

from collections import defaultdict


def evaluate(outcomes: list[dict]) -> dict:
    """outcomes JSONL レコード列から指標を返す.

    各 outcome は以下のキーを持つ:
      - target_removed: bool   (target NG が修正後に検出されないか)
      - new_ng_introduced: bool | None  (target 以外の NG が新規発生したか)
      - truth_pattern_ids: list[str]   (target の真の NG パターン id)
      - detected_after: list[str]      (修正後の検出結果)
    """
    n = len(outcomes)
    if n == 0:
        return {
            "n_samples": 0,
            "modification_success_rate": 0.0,
            "negative_transfer_rate": 0.0,
            "per_pattern_success": {},
            "per_pattern_support": {},
        }
    removed = sum(1 for r in outcomes if r.get("target_removed"))
    nt = sum(1 for r in outcomes if r.get("new_ng_introduced"))
    support: dict[str, int] = defaultdict(int)
    success_count: dict[str, int] = defaultdict(int)
    for r in outcomes:
        if r.get("new_ng_introduced") is None:
            continue
        for pid in r.get("truth_pattern_ids", []) or []:
            support[pid] += 1
            detected = r.get("detected_after") or []
            if pid not in detected:
                success_count[pid] += 1
    per_pattern = {p: success_count[p] / support[p] for p in support}
    return {
        "n_samples": n,
        "modification_success_rate": removed / n,
        "negative_transfer_rate": nt / n,
        "per_pattern_success": per_pattern,
        "per_pattern_support": dict(support),
    }
'''


def make_spec() -> EvaluatorSpec:
    test_cases = (
        TestCase(
            name="empty_outcomes",
            input={"outcomes": []},
            expected={
                "n_samples": 0,
                "modification_success_rate": 0.0,
                "negative_transfer_rate": 0.0,
            },
        ),
        TestCase(
            name="single_full_success",
            input={
                "outcomes": [
                    {
                        "target_removed": True,
                        "new_ng_introduced": False,
                        "truth_pattern_ids": ["pat_a"],
                        "detected_after": [],
                    }
                ]
            },
            expected={
                "n_samples": 1,
                "modification_success_rate": 1.0,
                "negative_transfer_rate": 0.0,
            },
        ),
        TestCase(
            name="single_full_failure",
            input={
                "outcomes": [
                    {
                        "target_removed": False,
                        "new_ng_introduced": True,
                        "truth_pattern_ids": ["pat_a"],
                        "detected_after": ["pat_a", "pat_b"],
                    }
                ]
            },
            expected={
                "n_samples": 1,
                "modification_success_rate": 0.0,
                "negative_transfer_rate": 1.0,
            },
        ),
    )
    return EvaluatorSpec(
        id="modification_success_v1",
        domain="nda",
        task_class="detect_and_modify",
        type="deterministic",
        input_signature=(
            (("target_document", "target"),),
            (
                ("findings", "ng_findings_v1"),
                ("modified_document", "modified_text_v1"),
            ),
        ),
        output_metrics=(
            "modification_success_rate",
            "negative_transfer_rate",
            "per_pattern_success",
        ),
        implementation=EVALUATOR_CODE,
        test_cases=test_cases,
        guardrails=(),
        sources=(
            "src/tsumiki/eval/modification.py (Phase 1〜4)",
            "docs/experiments/phase2_baseline_v0_2026-06-10.md",
            "docs/experiments/phase5b_skills_2026-06-19.md",
        ),
        generated_at="2026-06-19",
        approved_by="jncch",
        notes=(
            "Phase 1〜4 の compute_modification_report を Q3=B 決定関数として移植. "
            "Agent Skills 経由のロード前提. Phase 5b で paired diff +0.261 完全一致を確認済み."
        ),
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"流用蓄積ルート (default: {DEFAULT_ROOT.relative_to(PROJECT_ROOT)})",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    spec = make_spec()
    out_dir = save(args.root, spec)
    print(f"[done] saved evaluator to {out_dir.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
