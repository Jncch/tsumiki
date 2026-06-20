"""Phase 5a 辞書 ablation の集約スクリプト.

各 variant の outcomes JSONL から success_rate / negative_transfer / paired diff を計算、
V0 baseline との Δ paired diff を §3.2 ルールで寄与小・中・大に分類する。

入力ファイル名規約: `{variant_name}_{variant_id}_seed{seed}.jsonl`
  例: reuse_V0_seed42.jsonl, zerobase_V3_seed42.jsonl

使い方:
    uv run python experiments/aggregate_phase5a.py \\
        --outcomes-dir docs/experiments/phase5a_outcomes \\
        --seed 42 \\
        --baseline-paired-diff 0.261 \\
        --output-md docs/experiments/phase5a_ablation_$(date +%Y-%m-%d).md

設計: docs/experiments/phase5a_design.md §3
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Stats:
    n_samples: int
    success_rate: float
    negative_transfer_rate: float
    per_pattern_success: dict[str, float]
    per_pattern_support: dict[str, int]


def load_records(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def compute_stats(records: list[dict]) -> Stats:
    n = len(records)
    if n == 0:
        return Stats(0, 0.0, 0.0, {}, {})
    removed = sum(1 for r in records if r["target_removed"])
    nt = sum(1 for r in records if r["new_ng_introduced"])
    support: dict[str, int] = defaultdict(int)
    success_count: dict[str, int] = defaultdict(int)
    for r in records:
        if r["new_ng_introduced"] is None:
            continue
        for pid in r["truth_pattern_ids"]:
            support[pid] += 1
            if pid not in r["detected_after"]:
                success_count[pid] += 1
    per_pattern = {p: success_count[p] / support[p] for p in support}
    return Stats(
        n_samples=n,
        success_rate=removed / n,
        negative_transfer_rate=nt / n,
        per_pattern_success=per_pattern,
        per_pattern_support=dict(support),
    )


def classify_contribution(delta: float) -> str:
    """Δ paired diff から寄与判定. design §3.2."""
    if delta <= 0.05:
        return "寄与小"
    if delta <= 0.15:
        return "寄与中"
    return "寄与大"


VARIANT_LABELS: dict[str, str] = {
    "V0": "全部入り (baseline)",
    "V1": "「検出すべき」削除",
    "V2": "「紛らわしい」削除",
    "V3": "「対象条項」削除",
    "V4": "excerpt_examples 削除",
    "V5": "applicable_topics 削除",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--outcomes-dir",
        type=Path,
        default=Path("docs/experiments/phase5a_outcomes"),
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--variants",
        nargs="+",
        default=["V0", "V1", "V2", "V3", "V4", "V5"],
        help="集約対象 variant id（順序がそのまま表の順序になる）",
    )
    p.add_argument(
        "--output-md",
        type=Path,
        default=None,
        help="指定すると Markdown 表をこのパスに書き出す",
    )
    p.add_argument(
        "--baseline-paired-diff",
        type=float,
        default=None,
        help="Phase 2 baseline v0 seed=42 の paired diff (V0 一致ゲート用、±0.05 内かを判定)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    results: dict[str, tuple[Stats, Stats]] = {}
    missing: list[str] = []
    for variant_id in args.variants:
        reuse_path = args.outcomes_dir / f"reuse_{variant_id}_seed{args.seed}.jsonl"
        zerobase_path = args.outcomes_dir / f"zerobase_{variant_id}_seed{args.seed}.jsonl"
        ok = True
        if not reuse_path.is_file():
            missing.append(str(reuse_path))
            ok = False
        if not zerobase_path.is_file():
            missing.append(str(zerobase_path))
            ok = False
        if not ok:
            continue
        rs = compute_stats(load_records(reuse_path))
        zs = compute_stats(load_records(zerobase_path))
        results[variant_id] = (rs, zs)

    if missing:
        print("[warn] 以下の outcomes が見つかりません:")
        for m in missing:
            print(f"  - {m}")

    if "V0" not in results:
        print("[error] V0 baseline の結果が必須です", file=sys.stderr)
        return 1

    rs_v0, zs_v0 = results["V0"]
    baseline_paired = rs_v0.success_rate - zs_v0.success_rate

    if args.baseline_paired_diff is not None:
        gap = abs(baseline_paired - args.baseline_paired_diff)
        print(
            f"\n[gate] V0 paired diff = {baseline_paired:+.3f}, "
            f"参照値 = {args.baseline_paired_diff:+.3f}, |diff| = {gap:.3f}"
        )
        if gap > 0.05:
            print("[gate] WARNING: 参照値から 0.05 を超えて乖離。原因調査を推奨")

    lines: list[str] = []
    lines.append(f"# Phase 5a 辞書 ablation 結果 (seed={args.seed})")
    lines.append("")
    lines.append("設計: [phase5a_design.md](phase5a_design.md)")
    lines.append("")
    lines.append("## 1. 主指標 (paired diff = reuse - zerobase)")
    lines.append("")
    lines.append(
        "| variant | 操作 | reuse SR | zerobase SR | paired diff | Δ paired diff | 寄与判定 |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for vid in args.variants:
        if vid not in results:
            lines.append(
                f"| {vid} | {VARIANT_LABELS.get(vid, '?')} | - | - | - | - | (欠損) |"
            )
            continue
        rs, zs = results[vid]
        paired = rs.success_rate - zs.success_rate
        delta = baseline_paired - paired
        label = VARIANT_LABELS.get(vid, "?")
        if vid == "V0":
            verdict = "(baseline)"
            delta_str = "-"
        else:
            verdict = classify_contribution(delta)
            delta_str = f"{delta:+.3f}"
        lines.append(
            f"| {vid} | {label} | {rs.success_rate:.3f} | {zs.success_rate:.3f} | "
            f"{paired:+.3f} | {delta_str} | {verdict} |"
        )

    lines.append("")
    lines.append("判定ルール (設計 §3.2):")
    lines.append("- Δ paired diff ≤ 0.05 → 寄与小 (schema から除外可)")
    lines.append("- 0.05 < Δ ≤ 0.15 → 寄与中 (schema オプション項目)")
    lines.append("- Δ > 0.15 → 寄与大 (schema 必須項目)")
    lines.append("")
    lines.append("## 2. 副指標 (negative_transfer)")
    lines.append("")
    lines.append("| variant | reuse NT | zerobase NT | NT diff |")
    lines.append("| --- | --- | --- | --- |")
    for vid in args.variants:
        if vid not in results:
            lines.append(f"| {vid} | - | - | - |")
            continue
        rs, zs = results[vid]
        nt_diff = rs.negative_transfer_rate - zs.negative_transfer_rate
        lines.append(
            f"| {vid} | {rs.negative_transfer_rate:.3f} | "
            f"{zs.negative_transfer_rate:.3f} | {nt_diff:+.3f} |"
        )

    all_patterns: set[str] = set()
    for rs, zs in results.values():
        all_patterns.update(rs.per_pattern_success.keys())
    if all_patterns:
        lines.append("")
        lines.append("## 3. per-pattern reuse success_rate")
        lines.append("")
        header_cells = ["pattern_id", *args.variants]
        lines.append("| " + " | ".join(header_cells) + " |")
        lines.append("| " + " | ".join(["---"] * len(header_cells)) + " |")
        for pid in sorted(all_patterns):
            row = [pid]
            for vid in args.variants:
                if vid not in results:
                    row.append("-")
                    continue
                rs = results[vid][0]
                if pid in rs.per_pattern_success:
                    row.append(f"{rs.per_pattern_success[pid]:.3f}")
                else:
                    row.append("-")
            lines.append("| " + " | ".join(row) + " |")

    text = "\n".join(lines) + "\n"
    print()
    print(text)

    if args.output_md is not None:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(text, encoding="utf-8")
        print(f"[done] wrote {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
