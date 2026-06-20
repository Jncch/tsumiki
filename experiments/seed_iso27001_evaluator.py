"""ISO27001 用初期評価器を eval/generated/iso27001/detect_and_modify/<id>/ に保存する.

Phase 1〜4 で実装した tsumiki.eval.modification.compute_modification_report を、
NDA seed 評価器と同じ実装で ISO27001 ドメインに対応させる. outcomes JSONL の構造
(target_removed / new_ng_introduced / truth_pattern_ids / detected_after) はドメイン
非依存のため、実装は完全に同一でよい. 違いはメタデータ (id / domain / sources / notes).

Phase 6 で qwen 14B での generator パスが品質不足を示したため、流用パスを取るために
本 seed を投入する. generator パスの品質改善は Phase 7 以降 (クラウド GPT-5.4) の課題.

設計: docs/experiments/phase6_design.md §4.3
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tsumiki.goal import EvaluatorSpec, TestCase
from tsumiki.goal.store import save

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = PROJECT_ROOT / "src" / "tsumiki" / "eval" / "generated"

EVALUATOR_CODE = '''"""ISO27001 detect_and_modify 用評価器.

Phase 1〜4 で実装した tsumiki.eval.modification.compute_modification_report の移植.
outcomes JSONL の構造 (target_removed / new_ng_introduced / truth_pattern_ids /
detected_after) はドメイン非依存のため NDA seed 評価器と同じ実装で動く.

流用蓄積から動的ロードして使う.
"""

from __future__ import annotations

from collections import defaultdict


def evaluate(outcomes: list[dict]) -> dict:
    """outcomes JSONL レコード列から指標を返す.

    各 outcome は以下のキーを持つ:
      - target_removed: bool   (target 不備が修正後に検出されないか)
      - new_ng_introduced: bool | None  (target 以外の不備が新規発生したか)
      - truth_pattern_ids: list[str]   (target の真の不備 id)
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
                        "truth_pattern_ids": ["iso_access_least_privilege_missing"],
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
                        "truth_pattern_ids": ["iso_log_retention_undefined"],
                        "detected_after": [
                            "iso_log_retention_undefined",
                            "iso_backup_test_missing",
                        ],
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
        id="audit_findings_success_v1",
        domain="iso27001",
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
            "src/tsumiki/eval/generated/nda/detect_and_modify/modification_success_v1/ (Phase 5c)",
            "docs/experiments/phase6_design.md §4.3",
        ),
        generated_at="2026-06-19",
        approved_by="jncch",
        notes=(
            "ISO27001 ドメイン用. outcomes JSONL 構造はドメイン非依存のため NDA seed と "
            "同実装. qwen 14B での generator パスが品質不足を示したため (test_phase6_generator.py "
            "での verify 失敗を観測)、流用パスを取るために本 seed を投入. generator パスの "
            "品質改善は Phase 7 以降 (クラウド GPT-5.4) で検証する."
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
    out_dir = save(args.root.resolve(), spec)
    rel = out_dir.relative_to(PROJECT_ROOT) if str(out_dir).startswith(str(PROJECT_ROOT)) else out_dir
    print(f"[done] saved evaluator to {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
