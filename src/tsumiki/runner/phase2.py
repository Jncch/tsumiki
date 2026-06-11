"""Phase 2 統合 Runner.

責務:
- Phase 1 で構築した synth サンプル (NG 入り条項) を再利用
- 2 つの variant で T2 修正を実行: reuse / zerobase
- 修正後テキストを Phase 1 確定ベースライン (P2 = v0.3.0) の T1 検出器に流す
- 修正成功率と負の転移率を集計し MLflow に記録

各 variant について別 run を作る（experiment 内で run_name で識別）。
"""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import mlflow

from tsumiki.baseline import (
    detect_ng_patterns,
    modify_clause,
)
from tsumiki.data.clauses import CleanClause
from tsumiki.data.synthesis import ChatFn, SynthesisConfig, synthesize_sample
from tsumiki.eval.modification import (
    ModificationOutcome,
    ModificationReport,
    build_outcome,
    compute_modification_report,
)
from tsumiki.exp import log_run_params
from tsumiki.knowledge.loader import NGPattern, NGPatternBook


@dataclass(frozen=True)
class Phase2Outcome:
    variant: str  # "reuse" or "zerobase"
    n_samples: int
    report: ModificationReport


def _build_synth_only_samples(
    clean_clauses: Sequence[CleanClause],
    ng_patterns: Sequence[NGPattern],
    synth_config: SynthesisConfig,
    *,
    n_synth_per_pattern: int,
    synth_chat_fn: ChatFn,
    seed: int,
) -> list[tuple[str, str, tuple[str, ...]]]:
    """Phase 2 用に synth サンプルのみを作る.

    返り値: (sample_id, text, target_pattern_ids) のタプル列.
    重複なしで rng.sample により選択する (Phase 1 と同じバグ防止).
    """
    if not clean_clauses:
        raise ValueError("clean_clauses is empty")
    rng = random.Random(seed)
    out: list[tuple[str, str, tuple[str, ...]]] = []
    rotation = list(clean_clauses)
    for p in ng_patterns:
        n_pick = min(n_synth_per_pattern, len(rotation))
        chosen = rng.sample(rotation, n_pick)
        for c in chosen:
            try:
                s = synthesize_sample(c, [p], synth_config, synth_chat_fn)
            except Exception as e:  # noqa: BLE001
                print(
                    f"[phase2 synth] skip pattern={p.id} clause={c.clause_id} "
                    f"reason={type(e).__name__}: {e!s:.120}"
                )
                continue
            sid = f"{c.clause_id}|{p.id}"
            out.append((sid, s.text, (p.id,)))
    return out


def _dump_outcomes_jsonl(
    path: Path,
    outcomes: Sequence[ModificationOutcome],
    *,
    variant: str,
    seed: int,
) -> None:
    """outcome を JSONL に追記書き出し. レビュー対象抽出用."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for o in outcomes:
            rec = {
                "variant": variant,
                "seed": seed,
                "sample_id": o.sample_id,
                "original_text": o.original_text,
                "truth_pattern_ids": sorted(o.truth_pattern_ids),
                "modified_text": o.modified_text,
                "detected_after": sorted(o.detected_after),
                "target_removed": o.target_removed,
                "new_ng_introduced": o.new_ng_introduced,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run_phase2_variant(
    *,
    variant_name: str,
    samples: Sequence[tuple[str, str, tuple[str, ...]]],
    ng_book: NGPatternBook,
    modifier_chat_fn: ChatFn,
    detector_chat_fn: ChatFn,
    modifier_prompt_version: str,
    detector_prompt_version: str,
    run_params_extra: dict[str, object],
    run_name: str,
    outcomes_jsonl_path: Path | None = None,
) -> Phase2Outcome:
    """1 variant 分の T2 実行 + 評価 + MLflow 記録.

    outcomes_jsonl_path を指定すると個別 outcome を JSONL ダンプし、
    同ファイルを MLflow artifact にも添付する（人手レビュー用）。
    """
    patterns = ng_book.patterns
    outcomes: list[ModificationOutcome] = []
    for sid, text, target_ids in samples:
        try:
            modified = modify_clause(
                text, target_ids, patterns, modifier_chat_fn, modifier_prompt_version
            )
        except Exception as e:  # noqa: BLE001
            print(f"[phase2 modify] skip {sid} reason={type(e).__name__}: {e!s:.120}")
            continue
        detected = detect_ng_patterns(
            modified, patterns, detector_chat_fn, detector_prompt_version
        )
        outcomes.append(
            build_outcome(
                sample_id=sid,
                original_text=text,
                truth_pattern_ids=frozenset(target_ids),
                modified_text=modified,
                detected_after=detected,
            )
        )
    report = compute_modification_report(outcomes)

    if outcomes_jsonl_path is not None:
        seed_val = int(run_params_extra.get("seed", -1))
        _dump_outcomes_jsonl(
            outcomes_jsonl_path, outcomes, variant=variant_name, seed=seed_val
        )

    with mlflow.start_run(run_name=run_name):
        log_run_params(
            {
                "variant": variant_name,
                "modifier_prompt_version": modifier_prompt_version,
                "detector_prompt_version": detector_prompt_version,
                "ng_book_version": ng_book.version,
                "n_samples": report.n_samples,
                "n_target_removed": report.n_target_removed,
                "n_new_ng_introduced": report.n_new_ng_introduced,
                **run_params_extra,
            },
            require_full_set=False,
        )
        mlflow.log_metric("modification_success_rate", report.modification_success_rate)
        mlflow.log_metric("negative_transfer_rate", report.negative_transfer_rate)
        mlflow.log_metric("n_samples", float(report.n_samples))
        for pid, rate in report.per_pattern_success.items():
            mlflow.log_metric(f"success.{pid}", rate)
            mlflow.log_metric(f"support.{pid}", float(report.per_pattern_support[pid]))
        if outcomes_jsonl_path is not None and outcomes_jsonl_path.is_file():
            mlflow.log_artifact(str(outcomes_jsonl_path), artifact_path="outcomes")

    return Phase2Outcome(variant=variant_name, n_samples=report.n_samples, report=report)
