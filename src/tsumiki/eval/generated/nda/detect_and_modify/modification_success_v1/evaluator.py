"""NDA detect_and_modify 用評価器.

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
