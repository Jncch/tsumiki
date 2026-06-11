"""Phase 2 reuse variant の負の転移サンプル抽出スクリプト.

run_phase2_dryrun.py の --outcomes-dir で書き出した outcome JSONL を読み、
new_ng_introduced=True のサンプルを人手レビュー用 markdown に整形する。

使い方:
    uv run python experiments/extract_negative_transfer_review.py \\
        --outcomes-jsonl docs/experiments/phase2_outcomes/reuse_seed42.jsonl \\
        --output docs/experiments/phase2_negative_transfer_review_2026-06-10.md \\
        [--max-samples 20]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tsumiki.knowledge import load_ng_patterns


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--outcomes-jsonl",
        type=Path,
        required=True,
        help="run_phase2_dryrun.py が出力した outcome JSONL（reuse_seed*.jsonl）",
    )
    p.add_argument(
        "--output",
        type=Path,
        required=True,
        help="人手レビュー用 markdown 出力先",
    )
    p.add_argument(
        "--max-samples",
        type=int,
        default=20,
        help="抽出する最大件数",
    )
    p.add_argument(
        "--contract-type",
        default="nda",
        help="NG パターン辞書のドメイン名（説明文の併記用）",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.outcomes_jsonl.is_file():
        print(f"[error] {args.outcomes_jsonl} が存在しません.")
        return 1

    book = load_ng_patterns(args.contract_type)
    pattern_by_id = {p.id: p for p in book.patterns}

    records: list[dict] = []
    with args.outcomes_jsonl.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))

    if not records:
        print("[error] outcomes JSONL が空です.")
        return 1

    seed = records[0].get("seed")
    variant = records[0].get("variant")
    print(f"[load] variant={variant} seed={seed} total={len(records)}")

    nt = [r for r in records if r.get("new_ng_introduced")]
    print(f"[filter] new_ng_introduced=True : {len(nt)} / {len(records)} samples")

    # truth 側 pattern_id 順に並べる（パターン横断でバランスを見たいため）
    nt.sort(key=lambda r: (tuple(r.get("truth_pattern_ids", [])), r.get("sample_id", "")))

    # パターンごとに均等に拾う（先頭から順に最大 max_samples）
    by_truth: dict[tuple[str, ...], list[dict]] = {}
    for r in nt:
        key = tuple(r.get("truth_pattern_ids", []))
        by_truth.setdefault(key, []).append(r)

    selected: list[dict] = []
    if nt:
        # ラウンドロビンで各 truth から 1 件ずつ拾い、上限まで
        cursors = {k: 0 for k in by_truth}
        while len(selected) < args.max_samples:
            advanced = False
            for k in by_truth:
                if cursors[k] < len(by_truth[k]):
                    selected.append(by_truth[k][cursors[k]])
                    cursors[k] += 1
                    advanced = True
                    if len(selected) >= args.max_samples:
                        break
            if not advanced:
                break

    args.output.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(
        f"# Phase 2 reuse 負の転移 人手レビュー（seed={seed}, "
        f"variant={variant}, 抽出 {len(selected)}/{len(nt)} 件）"
    )
    lines.append("")
    lines.append(
        "Phase 2 ベースライン v0 の reuse variant で `new_ng_introduced=True` と"
        "判定されたサンプルを抽出した。各サンプルにつき、`detected_after - truth_pattern_ids` の"
        "差分 NG ID を「新規検出 NG」として列挙する。"
    )
    lines.append("")
    lines.append("レビューの目的: 各差分 NG が **真の負の転移**（修正で本当に NG を追加した）か、")
    lines.append("**T1 検出器の FP**（実際には NG でない）かを判定する。")
    lines.append("")
    lines.append("判定欄: `[ ]` の中に `T` (真の負の転移) / `F` (FP) / `?` (判断保留) を記入。")
    lines.append("")
    lines.append("## サマリ")
    lines.append("")
    lines.append(f"| 項目 | 値 |")
    lines.append(f"| --- | --- |")
    lines.append(f"| 元 outcomes JSONL | `{args.outcomes_jsonl.relative_to(args.outcomes_jsonl.parents[2])}` |")
    lines.append(f"| variant | {variant} |")
    lines.append(f"| seed | {seed} |")
    lines.append(f"| 全サンプル数 | {len(records)} |")
    lines.append(f"| 負の転移サンプル数 | {len(nt)} ({len(nt)/len(records)*100:.1f}%) |")
    lines.append(f"| 抽出件数 | {len(selected)} |")
    lines.append("")
    lines.append("## レビュー対象")
    lines.append("")

    for i, r in enumerate(selected, start=1):
        sid = r["sample_id"]
        truth = list(r["truth_pattern_ids"])
        detected = list(r["detected_after"])
        new_ngs = sorted(set(detected) - set(truth))
        target_removed = r.get("target_removed", False)

        lines.append(f"### {i}. {sid}")
        lines.append("")
        lines.append(f"- truth NG: `{', '.join(truth) or '(なし)'}`")
        lines.append(f"- 修正後 detected: `{', '.join(detected) or '(なし)'}`")
        lines.append(f"- 新規検出 NG: `{', '.join(new_ngs)}`")
        lines.append(f"- target_removed: `{target_removed}`")
        lines.append("")
        lines.append("**原文**:")
        lines.append("")
        lines.append("```")
        lines.append(r["original_text"])
        lines.append("```")
        lines.append("")
        lines.append("**修正後**:")
        lines.append("")
        lines.append("```")
        lines.append(r["modified_text"])
        lines.append("```")
        lines.append("")
        lines.append("**新規検出 NG の説明**:")
        lines.append("")
        for pid in new_ngs:
            p = pattern_by_id.get(pid)
            if p is None:
                lines.append(f"- `{pid}`: (不明パターン)")
                continue
            # 多行 description は最初の意味のある行のみ抜粋
            desc = (p.description or "").strip()
            first = desc.splitlines()[0] if desc else ""
            lines.append(f"- `{pid}` ({p.name}): {first}")
        lines.append("")
        lines.append("**判定**:")
        lines.append("")
        for pid in new_ngs:
            lines.append(f"- [ ] `{pid}`: 判定 (T=真の負の転移 / F=FP / ?=保留) 　コメント:")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 集計欄（レビュー完了後に記入）")
    lines.append("")
    lines.append(
        "| 項目 | 値 |"
    )
    lines.append("| --- | --- |")
    lines.append("| T 判定の差分 NG 件数 | |")
    lines.append("| F 判定の差分 NG 件数 | |")
    lines.append("| ? 判定の差分 NG 件数 | |")
    lines.append("| 真の負の転移率（推定） | |")
    lines.append("| T1 検出器 FP に起因する見かけの負の転移率（推定） | |")
    lines.append("")

    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"[ok] wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
