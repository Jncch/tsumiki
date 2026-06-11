"""Phase 1 ベースラインの複数 seed 集計.

MLflow experiment "phase1_baseline_v0" 内の同条件 (model, n_synth_per_pattern, n_clean)
run を seed 横断で集計し、macro/per-pattern 指標の平均・標準偏差・95% CI を出力する。

n が小さい (典型 3) ため t 分布で CI を計算する。

使い方:
    uv run python experiments/aggregate_phase1_seeds.py
"""

from __future__ import annotations

import argparse
import math
import statistics
from collections import defaultdict

import mlflow
from scipy import stats

from tsumiki.knowledge import load_ng_patterns


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--experiment", default="phase1_baseline_v0")
    p.add_argument(
        "--model",
        default="hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M",
    )
    p.add_argument("--n-synth-per-pattern", default="10")
    p.add_argument("--n-clean", default="14")
    p.add_argument("--tracking-uri", default="file:./mlruns")
    return p.parse_args()


def t_ci_95(values: list[float]) -> tuple[float, float, float, float]:
    """平均・std・CI 下限・上限を返す. n<2 のときは std=0, CI 幅 0."""
    mean = statistics.mean(values)
    if len(values) < 2:
        return mean, 0.0, mean, mean
    std = statistics.stdev(values)
    n = len(values)
    t_crit = float(stats.t.ppf(0.975, df=n - 1))
    margin = t_crit * std / math.sqrt(n)
    return mean, std, mean - margin, mean + margin


def fmt_summary(values: list[float]) -> str:
    mean, std, lo, hi = t_ci_95(values)
    return f"mean={mean:.3f} std={std:.3f} 95%CI=[{lo:.3f}, {hi:.3f}]"


def main() -> int:
    args = parse_args()
    mlflow.set_tracking_uri(args.tracking_uri)
    client = mlflow.MlflowClient()
    exp = client.get_experiment_by_name(args.experiment)
    if exp is None:
        print(f"[error] experiment '{args.experiment}' not found")
        return 1

    runs = client.search_runs(exp.experiment_id, run_view_type=3)

    # 同条件 (model, n_synth_per_pattern, n_clean) のみ.
    # status=FINISHED に限定して失敗 run を除外.
    cfg = {
        "model": args.model,
        "n_synth_per_pattern": args.n_synth_per_pattern,
        "n_clean": args.n_clean,
    }
    matching = [
        r
        for r in runs
        if r.info.status == "FINISHED"
        and all(r.data.params.get(k) == v for k, v in cfg.items())
    ]
    if not matching:
        print(f"[error] no matching runs for config: {cfg}")
        return 1

    seeds = sorted({int(r.data.params.get("seed", "-1")) for r in matching})
    print("=== Phase 1 baseline aggregation ===")
    print(f"experiment : {args.experiment}")
    print(f"runs       : {len(matching)}")
    print(f"seeds      : {seeds}")
    print(f"model      : {args.model}")
    print(f"n_synth/p  : {args.n_synth_per_pattern}")
    print(f"n_clean    : {args.n_clean}")
    print()

    # Metric を seed 横断で集める
    metric_groups: dict[str, list[float]] = defaultdict(list)
    for r in matching:
        for k, v in r.data.metrics.items():
            metric_groups[k].append(v)

    # 集約指標
    print("=== macro / weighted (TEST) ===")
    for k in [
        "test.macro_recall",
        "test.macro_precision",
        "test.macro_fbeta",
        "test.weighted_recall",
        "test.weighted_precision",
        "test.weighted_fbeta",
    ]:
        if k in metric_groups:
            print(f"  {k:30s} {fmt_summary(metric_groups[k])}")

    print()
    print("=== macro (VAL) ===")
    for k in ["val.macro_recall", "val.macro_precision", "val.macro_fbeta"]:
        if k in metric_groups:
            print(f"  {k:30s} {fmt_summary(metric_groups[k])}")

    # per-pattern (TEST)
    book = load_ng_patterns("nda")
    print()
    print("=== per-pattern recall (TEST) ===")
    print(f"  {'pattern_id':35s} {'mean':>6s} {'std':>6s} {'95%CI':>22s}")
    for p in book.patterns:
        key = f"test.recall.{p.id}"
        if key in metric_groups:
            mean, std, lo, hi = t_ci_95(metric_groups[key])
            print(
                f"  {p.id:35s} {mean:6.3f} {std:6.3f}   [{lo:6.3f}, {hi:6.3f}]"
            )
    print()
    print("=== per-pattern precision (TEST) ===")
    print(f"  {'pattern_id':35s} {'mean':>6s} {'std':>6s} {'95%CI':>22s}")
    for p in book.patterns:
        key = f"test.precision.{p.id}"
        if key in metric_groups:
            mean, std, lo, hi = t_ci_95(metric_groups[key])
            print(
                f"  {p.id:35s} {mean:6.3f} {std:6.3f}   [{lo:6.3f}, {hi:6.3f}]"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
