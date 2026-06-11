"""Phase 1 統合 Runner.

責務:
- CleanClause + NG パターン辞書 → 合成サンプル + clean サンプル混在のラベル集合
- 層化分割 (train/val/test)
- ベースライン予測 (val または test)
- 評価指標計算と MLflow 記録

合成と予測は別々の ChatFn を渡せる（モデルを変えて比較するため）。
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

import mlflow

from tsumiki.baseline import predict_clauses
from tsumiki.data.clauses import CleanClause
from tsumiki.data.synthesis import ChatFn, SynthesisConfig, synthesize_sample
from tsumiki.eval import ClauseLabel, MetricsReport, compute_metrics
from tsumiki.eval.split import SplitConfig, stratified_split
from tsumiki.exp import log_metrics_report, log_run_params
from tsumiki.knowledge.loader import NGPattern, NGPatternBook, TopicVocab


@dataclass(frozen=True)
class Phase1Outcome:
    """Phase 1 end-to-end 実行の結果."""

    n_train: int
    n_val: int
    n_test: int
    val_report: MetricsReport
    test_report: MetricsReport


def _sample_to_label(
    clean: CleanClause,
    text: str,
    ng_pattern_ids: tuple[str, ...],
) -> ClauseLabel:
    return ClauseLabel(
        clause_id=f"{clean.clause_id}|{'+'.join(ng_pattern_ids) if ng_pattern_ids else 'clean'}",
        contract_type=clean.contract_type,
        text=text,
        ng_pattern_ids=frozenset(ng_pattern_ids),
    )


def build_labeled_samples(
    clean_clauses: Sequence[CleanClause],
    ng_patterns: Sequence[NGPattern],
    synth_config: SynthesisConfig,
    *,
    n_synth_per_pattern: int,
    n_clean: int,
    synth_chat_fn: ChatFn,
    seed: int,
) -> list[ClauseLabel]:
    """clean と synth を混ぜたラベル付きデータ集合を作る.

    - 各 NG パターンについて n_synth_per_pattern 件、clean clause を循環的に選び注入
    - n_clean 件の clean サンプルを別途追加 (LLM 呼び出しなし)
    - 同じ clean clause を複数の synth に流用するため、入力規模に対しサンプル数は線形以上に増える
    """
    if not clean_clauses:
        raise ValueError("clean_clauses is empty")
    rng = random.Random(seed)
    labels: list[ClauseLabel] = []

    # clean サンプル
    clean_pool = list(clean_clauses)
    for i in range(min(n_clean, len(clean_pool))):
        c = clean_pool[i]
        s = synthesize_sample(c, [], synth_config, synth_chat_fn)
        labels.append(_sample_to_label(c, s.text, s.ng_pattern_ids))

    # 各パターンについて synth サンプル.
    # rng.sample で重複なし選択 (同じ (clean, pattern, seed) は同一 LLM 出力になるため
    # 重複させる意味がなく、また下流の clause_id 衝突を防ぐ).
    # n_synth_per_pattern > len(clean_clauses) のときは available 件数で頭打ち.
    rotation = list(clean_clauses)
    skipped = 0
    for p in ng_patterns:
        n_pick = min(n_synth_per_pattern, len(rotation))
        if n_pick < n_synth_per_pattern:
            print(
                f"[build_labeled_samples] {p.id}: requested {n_synth_per_pattern} > "
                f"available clean {len(rotation)}, capped to {n_pick}"
            )
        chosen = rng.sample(rotation, n_pick)
        for c in chosen:
            try:
                s = synthesize_sample(c, [p], synth_config, synth_chat_fn)
            except Exception as e:  # noqa: BLE001 — LLM 由来の任意の例外を捕捉
                skipped += 1
                print(
                    f"[build_labeled_samples] skip synth pattern={p.id} "
                    f"clause={c.clause_id} reason={type(e).__name__}: {e!s:.120}"
                )
                continue
            labels.append(_sample_to_label(c, s.text, s.ng_pattern_ids))
    if skipped:
        print(f"[build_labeled_samples] total skipped synth = {skipped}")
    return labels


def evaluate_baseline(
    labels: Sequence[ClauseLabel],
    ng_patterns: Sequence[NGPattern],
    chat_fn: ChatFn,
    prompt_version: str | None = None,
    topics: Sequence[TopicVocab] = (),
) -> MetricsReport:
    """ClauseLabel をベースライン予測器で評価する.

    prompt_version を渡さない場合は baseline モジュールの LATEST を使う。
    v0.5.0 以降のトピック照合プロンプトでは topics を必須で渡す。
    """
    pseudo_clauses = [
        CleanClause(
            clause_id=label.clause_id,
            contract_type=label.contract_type,
            source_id="phase1",
            article_no="-",
            text=label.text,
        )
        for label in labels
    ]
    kwargs: dict[str, object] = {}
    if prompt_version:
        kwargs["prompt_version"] = prompt_version
    if topics:
        kwargs["topics"] = topics
    preds = predict_clauses(pseudo_clauses, ng_patterns, chat_fn, **kwargs)  # type: ignore[arg-type]
    pattern_ids = [p.id for p in ng_patterns]
    return compute_metrics(labels, preds, pattern_ids)


def run_phase1(
    *,
    clean_clauses: Sequence[CleanClause],
    ng_book: NGPatternBook,
    synth_config: SynthesisConfig,
    split_config: SplitConfig,
    n_synth_per_pattern: int,
    n_clean: int,
    synth_chat_fn: ChatFn,
    baseline_chat_fn: ChatFn,
    baseline_model: str,
    baseline_quant_tag: str,
    baseline_prompt_version: str,
    run_name: str,
) -> Phase1Outcome:
    """End-to-end. 結果は MLflow に記録し Phase1Outcome を返す."""
    severity_by_id = {p.id: p.severity for p in ng_book.patterns}

    labels = build_labeled_samples(
        clean_clauses,
        ng_book.patterns,
        synth_config,
        n_synth_per_pattern=n_synth_per_pattern,
        n_clean=n_clean,
        synth_chat_fn=synth_chat_fn,
        seed=split_config.seed,
    )

    train, val, test = stratified_split(
        labels, lambda lab: lab.ng_pattern_ids, severity_by_id, split_config
    )

    with mlflow.start_run(run_name=run_name):
        log_run_params(
            {
                "model": baseline_model,
                "quantization_tag": baseline_quant_tag,
                "prompt_version": baseline_prompt_version,
                "seed": split_config.seed,
                "temperature": synth_config.temperature,
                "contract_type": ng_book.contract_type,
                "phase": "phase1_baseline",
                "synth_model": synth_config.model,
                "synth_prompt_version": synth_config.prompt_version,
                "n_train": len(train),
                "n_val": len(val),
                "n_test": len(test),
                "n_synth_per_pattern": n_synth_per_pattern,
                "n_clean": n_clean,
                "ng_book_version": ng_book.version,
            }
        )
        val_report = evaluate_baseline(
            val,
            ng_book.patterns,
            baseline_chat_fn,
            prompt_version=baseline_prompt_version,
            topics=ng_book.topics,
        )
        log_metrics_report(val_report, prefix="val")
        test_report = evaluate_baseline(
            test,
            ng_book.patterns,
            baseline_chat_fn,
            prompt_version=baseline_prompt_version,
            topics=ng_book.topics,
        )
        log_metrics_report(test_report, prefix="test")

    return Phase1Outcome(
        n_train=len(train),
        n_val=len(val),
        n_test=len(test),
        val_report=val_report,
        test_report=test_report,
    )
