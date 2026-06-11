"""Phase 3 頑健性: v0.1.0 と v0.1.1 (言い換え版) を比較集計するスクリプト.

各 variant (reuse/zerobase) × 各 prompt version (v0.1.0/v0.1.1) の outcome JSONL を読み、
- success_rate
- negative_transfer_rate
- per-pattern success
- v0.1.0 vs v0.1.1 の差分
を集計する。Phase 3 ゲート: タスク記述（プロンプト）の言い換えで結果がぶれないこと。

使い方:
    uv run python experiments/aggregate_phase3_robustness.py \\
        --v010-dir docs/experiments/phase2_outcomes \\
        --v011-dir docs/experiments/phase3_outcomes \\
        --seed 42
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Stats:
    n_samples: int
    n_target_removed: int
    n_new_ng_introduced: int
    per_pattern_support: dict[str, int]
    per_pattern_success: dict[str, float]

    @property
    def success_rate(self) -> float:
        return self.n_target_removed / self.n_samples if self.n_samples else 0.0

    @property
    def negative_transfer_rate(self) -> float:
        return self.n_new_ng_introduced / self.n_samples if self.n_samples else 0.0


def load_records(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def compute_stats(records: list[dict]) -> Stats:
    support: dict[str, int] = defaultdict(int)
    success_count: dict[str, int] = defaultdict(int)
    n_removed = 0
    n_new = 0
    for r in records:
        if r["target_removed"]:
            n_removed += 1
        if r["new_ng_introduced"]:
            n_new += 1
        for pid in r["truth_pattern_ids"]:
            support[pid] += 1
            if pid not in r["detected_after"]:
                success_count[pid] += 1
    per_pattern_success = {
        pid: success_count[pid] / support[pid] for pid in support
    }
    return Stats(
        n_samples=len(records),
        n_target_removed=n_removed,
        n_new_ng_introduced=n_new,
        per_pattern_support=dict(support),
        per_pattern_success=per_pattern_success,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--v010-dir", type=Path, required=True)
    p.add_argument("--v011-dir", type=Path, required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--output-md",
        type=Path,
        default=Path("docs/experiments/phase3_robustness_2026-06-10.md"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    seed = args.seed

    v010_reuse_path = args.v010_dir / f"reuse_seed{seed}.jsonl"
    v010_zerobase_path = args.v010_dir / f"zerobase_seed{seed}.jsonl"
    v011_reuse_path = args.v011_dir / f"reuse_v011_seed{seed}.jsonl"
    v011_zerobase_path = args.v011_dir / f"zerobase_v011_seed{seed}.jsonl"

    paths = {
        "reuse_v0.1.0": v010_reuse_path,
        "zerobase_v0.1.0": v010_zerobase_path,
        "reuse_v0.1.1": v011_reuse_path,
        "zerobase_v0.1.1": v011_zerobase_path,
    }

    stats: dict[str, Stats] = {}
    for label, path in paths.items():
        records = load_records(path)
        stats[label] = compute_stats(records)
        print(
            f"[load] {label:24s} n={stats[label].n_samples:3d} "
            f"success={stats[label].success_rate:.3f} "
            f"neg_transfer={stats[label].negative_transfer_rate:.3f}"
        )

    # markdown を組み立てる
    md: list[str] = []
    md.append(f"# Phase 3 頑健性: 言い換えプロンプト試験（seed={seed}, 2026-06-10）")
    md.append("")
    md.append(
        "検証計画書 §5.2 Phase 3 のゲート: 「タスク記述の言い換え・シード変更で再実行し安定性を確認」。"
    )
    md.append("シード変更は本走 (seed 42/43/44) で既に確認済み。本ドキュメントは **タスク記述（プロンプト）の言い換え** に対する安定性を測る。")
    md.append("")
    md.append("## 0. 設計")
    md.append("")
    md.append("| 項目 | 値 |")
    md.append("| --- | --- |")
    md.append(f"| seed | {seed}（再現のため固定） |")
    md.append("| プロンプト v0.1.0 | Phase 2 ベースライン v0 で使用したオリジナル |")
    md.append("| プロンプト v0.1.1 | 同意味・別表現の言い換え版 |")
    md.append(
        "| 言い換え方針 | 「あなたは~担当です」→「次の業務を担当してください」、見出し記号 `#` → `【】`、"
        "「制約」→「守るべき条件」等。意味と入力スロットは保つ。 |"
    )
    md.append(f"| サンプル | seed={seed} の n_synth_per_pattern=5（40〜45 件） |")
    md.append("| モデル / 評価条件 | Phase 2 ベースライン v0 と同一 (qwen2.5 14B Q4_K_M, temperature=0) |")
    md.append("| T1 検出器 | Phase 1 P2 ベースライン (v0.3.0) |")
    md.append("")

    md.append("## 1. 主要指標の比較")
    md.append("")
    md.append("### 1.1 reuse variant")
    md.append("")
    md.append("| 指標 | v0.1.0 | v0.1.1 | 差 (v0.1.1 - v0.1.0) |")
    md.append("| --- | --- | --- | --- |")
    md.append(
        f"| n_samples | {stats['reuse_v0.1.0'].n_samples} | {stats['reuse_v0.1.1'].n_samples} | "
        f"{stats['reuse_v0.1.1'].n_samples - stats['reuse_v0.1.0'].n_samples:+d} |"
    )
    sr_diff_reuse = stats["reuse_v0.1.1"].success_rate - stats["reuse_v0.1.0"].success_rate
    nt_diff_reuse = (
        stats["reuse_v0.1.1"].negative_transfer_rate - stats["reuse_v0.1.0"].negative_transfer_rate
    )
    md.append(
        f"| success_rate | {stats['reuse_v0.1.0'].success_rate:.3f} | "
        f"{stats['reuse_v0.1.1'].success_rate:.3f} | {sr_diff_reuse:+.3f} |"
    )
    md.append(
        f"| negative_transfer_rate | {stats['reuse_v0.1.0'].negative_transfer_rate:.3f} | "
        f"{stats['reuse_v0.1.1'].negative_transfer_rate:.3f} | {nt_diff_reuse:+.3f} |"
    )
    md.append("")
    md.append("### 1.2 zerobase variant")
    md.append("")
    md.append("| 指標 | v0.1.0 | v0.1.1 | 差 (v0.1.1 - v0.1.0) |")
    md.append("| --- | --- | --- | --- |")
    md.append(
        f"| n_samples | {stats['zerobase_v0.1.0'].n_samples} | {stats['zerobase_v0.1.1'].n_samples} | "
        f"{stats['zerobase_v0.1.1'].n_samples - stats['zerobase_v0.1.0'].n_samples:+d} |"
    )
    sr_diff_zb = (
        stats["zerobase_v0.1.1"].success_rate - stats["zerobase_v0.1.0"].success_rate
    )
    nt_diff_zb = (
        stats["zerobase_v0.1.1"].negative_transfer_rate
        - stats["zerobase_v0.1.0"].negative_transfer_rate
    )
    md.append(
        f"| success_rate | {stats['zerobase_v0.1.0'].success_rate:.3f} | "
        f"{stats['zerobase_v0.1.1'].success_rate:.3f} | {sr_diff_zb:+.3f} |"
    )
    md.append(
        f"| negative_transfer_rate | {stats['zerobase_v0.1.0'].negative_transfer_rate:.3f} | "
        f"{stats['zerobase_v0.1.1'].negative_transfer_rate:.3f} | {nt_diff_zb:+.3f} |"
    )
    md.append("")

    md.append("### 1.3 paired diff (reuse - zerobase)")
    md.append("")
    md.append("再利用の優位性 (success_rate ベース) が言い換えで保たれるか確認:")
    md.append("")
    md.append("| 指標 | v0.1.0 | v0.1.1 |")
    md.append("| --- | --- | --- |")
    paired_v010 = stats["reuse_v0.1.0"].success_rate - stats["zerobase_v0.1.0"].success_rate
    paired_v011 = stats["reuse_v0.1.1"].success_rate - stats["zerobase_v0.1.1"].success_rate
    md.append(f"| paired diff (success_rate) | {paired_v010:+.3f} | {paired_v011:+.3f} |")
    md.append("")

    md.append("## 2. パターン別 success_rate 比較")
    md.append("")
    md.append("### 2.1 reuse")
    md.append("")
    md.append("| pattern_id | v0.1.0 | v0.1.1 | 差 |")
    md.append("| --- | --- | --- | --- |")
    pattern_ids = sorted(
        set(stats["reuse_v0.1.0"].per_pattern_success.keys())
        | set(stats["reuse_v0.1.1"].per_pattern_success.keys())
    )
    for pid in pattern_ids:
        a = stats["reuse_v0.1.0"].per_pattern_success.get(pid, 0.0)
        b = stats["reuse_v0.1.1"].per_pattern_success.get(pid, 0.0)
        md.append(f"| {pid} | {a:.3f} | {b:.3f} | {b - a:+.3f} |")
    md.append("")

    md.append("### 2.2 zerobase")
    md.append("")
    md.append("| pattern_id | v0.1.0 | v0.1.1 | 差 |")
    md.append("| --- | --- | --- | --- |")
    pattern_ids = sorted(
        set(stats["zerobase_v0.1.0"].per_pattern_success.keys())
        | set(stats["zerobase_v0.1.1"].per_pattern_success.keys())
    )
    for pid in pattern_ids:
        a = stats["zerobase_v0.1.0"].per_pattern_success.get(pid, 0.0)
        b = stats["zerobase_v0.1.1"].per_pattern_success.get(pid, 0.0)
        md.append(f"| {pid} | {a:.3f} | {b:.3f} | {b - a:+.3f} |")
    md.append("")

    md.append("## 3. 安定性判定")
    md.append("")
    md.append("| 指標 | reuse 変化 | zerobase 変化 | コメント |")
    md.append("| --- | --- | --- | --- |")
    md.append(
        f"| success_rate | {sr_diff_reuse:+.3f} | {sr_diff_zb:+.3f} | "
        "(後段で記述) |"
    )
    md.append(
        f"| negative_transfer_rate | {nt_diff_reuse:+.3f} | {nt_diff_zb:+.3f} | "
        "T1 検出器 FP が支配的なので変化は本質的でない |"
    )
    md.append(
        f"| paired diff | {paired_v010:+.3f} → {paired_v011:+.3f} | - | "
        "再利用の優位性が言い換えで保たれるか |"
    )
    md.append("")

    md.append("## 4. 結論（暫定）")
    md.append("")
    md.append("（実走後に記述。判断基準:")
    md.append("- success_rate の差が ±0.1 以内かつ paired diff が同方向 → **頑健性 OK**")
    md.append("- success_rate の差が ±0.15 を超える、または paired diff が逆転 → **頑健性に課題あり**")
    md.append("- いずれにせよ Phase 3 ゲートは「不安定なら否定的結論」なので、reuse の優位性が言い換えで残るかが核 ）")
    md.append("")

    md.append("## 5. 関連")
    md.append("")
    md.append("- Phase 2 ベースライン v0: [`phase2_baseline_v0_2026-06-10.md`](phase2_baseline_v0_2026-06-10.md)")
    md.append("- 人手レビュー結果: [`phase2_negative_transfer_review_results_2026-06-10.md`](phase2_negative_transfer_review_results_2026-06-10.md)")
    md.append("- v0.1.0 outcomes: [`phase2_outcomes/reuse_seed42.jsonl`](phase2_outcomes/reuse_seed42.jsonl)")
    md.append("- v0.1.1 outcomes: [`phase3_outcomes/reuse_v011_seed42.jsonl`](phase3_outcomes/reuse_v011_seed42.jsonl)")
    md.append("- 修正プロンプト定義: [`../../src/tsumiki/baseline/ng_modifier.py`](../../src/tsumiki/baseline/ng_modifier.py)")
    md.append("- 検証計画書 §5.2: [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md)")
    md.append("")

    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text("\n".join(md), encoding="utf-8")
    print(f"[ok] wrote {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
