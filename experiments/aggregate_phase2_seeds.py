"""Phase 2 の複数 seed outcomes JSONL から 3 seed mean ± std ± 95% CI を算出.

各 variant (reuse/zerobase) の outcomes JSONL を seed ごとに読み込み、
- success_rate
- negative_transfer_rate
- per-pattern success_rate
- paired diff (reuse - zerobase) per seed
を集計する。t 分布 (df=n-1) で 95% CI を計算。

使い方:
    uv run python experiments/aggregate_phase2_seeds.py \\
        --outcomes-dir docs/experiments/phase2_outcomes_azure \\
        --suffix _azure_gpt5_4 \\
        --seeds 42 43 44
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from scipy import stats


@dataclass(frozen=True)
class Stats:
    n_samples: int
    success_rate: float
    negative_transfer_rate: float
    per_pattern_success: dict[str, float]
    per_pattern_support: dict[str, int]


def t_ci_95(values: list[float]) -> tuple[float, float, float, float]:
    mean = statistics.mean(values)
    if len(values) < 2:
        return mean, 0.0, mean, mean
    std = statistics.stdev(values)
    n = len(values)
    t_crit = float(stats.t.ppf(0.975, df=n - 1))
    margin = t_crit * std / math.sqrt(n)
    return mean, std, mean - margin, mean + margin


def fmt(values: list[float]) -> str:
    mean, std, lo, hi = t_ci_95(values)
    return f"{mean:.3f} ± {std:.3f}  95%CI=[{lo:.3f}, {hi:.3f}]"


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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--outcomes-dir", type=Path, required=True)
    p.add_argument(
        "--suffix",
        default="",
        help="variant 名の suffix（例: '_azure_gpt5_4'）。ファイル名は <variant><suffix>_seed<seed>.jsonl 想定",
    )
    p.add_argument("--seeds", type=int, nargs="+", required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    # 各 seed × 各 variant の stats を集める
    by_variant: dict[str, list[Stats]] = {"reuse": [], "zerobase": []}
    for seed in args.seeds:
        for variant in ("reuse", "zerobase"):
            path = args.outcomes_dir / f"{variant}{args.suffix}_seed{seed}.jsonl"
            if not path.is_file():
                print(f"[error] {path} が見つかりません")
                return 1
            records = load_records(path)
            by_variant[variant].append(compute_stats(records))
            print(
                f"[load] {variant} seed={seed}: n={by_variant[variant][-1].n_samples} "
                f"success={by_variant[variant][-1].success_rate:.3f} "
                f"neg={by_variant[variant][-1].negative_transfer_rate:.3f}"
            )

    print()
    print("=" * 60)
    print(f"集約: seeds={args.seeds}, suffix={args.suffix!r}")
    print("=" * 60)

    # 主要指標
    for variant in ("reuse", "zerobase"):
        sr = [s.success_rate for s in by_variant[variant]]
        nt = [s.negative_transfer_rate for s in by_variant[variant]]
        print(f"\n[{variant}]")
        print(f"  success_rate         : {fmt(sr)}")
        print(f"  negative_transfer    : {fmt(nt)}")

    # paired diff (reuse - zerobase) per seed
    print("\n[paired diff (reuse - zerobase)]")
    paired_sr = [
        by_variant["reuse"][i].success_rate - by_variant["zerobase"][i].success_rate
        for i in range(len(args.seeds))
    ]
    paired_nt = [
        by_variant["reuse"][i].negative_transfer_rate
        - by_variant["zerobase"][i].negative_transfer_rate
        for i in range(len(args.seeds))
    ]
    print(f"  success_rate diff    : {fmt(paired_sr)}")
    print(f"  negative_transfer diff: {fmt(paired_nt)}")
    print(f"  per-seed success diff: {[round(x, 3) for x in paired_sr]}")
    print(f"  per-seed neg diff    : {[round(x, 3) for x in paired_nt]}")

    # per-pattern
    all_patterns: set[str] = set()
    for variant in ("reuse", "zerobase"):
        for s in by_variant[variant]:
            all_patterns.update(s.per_pattern_success.keys())
    print("\n[per-pattern success_rate mean ± std]")
    print(f"{'pattern_id':35s} {'reuse':25s} {'zerobase':25s}  diff")
    for pid in sorted(all_patterns):
        r_vals = [s.per_pattern_success.get(pid, 0.0) for s in by_variant["reuse"]]
        z_vals = [s.per_pattern_success.get(pid, 0.0) for s in by_variant["zerobase"]]
        r_mean, _, _, _ = t_ci_95(r_vals)
        z_mean, _, _, _ = t_ci_95(z_vals)
        r_str = f"{r_mean:.3f} ± {statistics.stdev(r_vals) if len(r_vals) > 1 else 0:.3f}"
        z_str = f"{z_mean:.3f} ± {statistics.stdev(z_vals) if len(z_vals) > 1 else 0:.3f}"
        diff = r_mean - z_mean
        marker = " *reuse" if diff >= 0.1 else " *zero" if diff <= -0.1 else ""
        print(f"{pid:35s} {r_str:25s} {z_str:25s} {diff:+.3f}{marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
