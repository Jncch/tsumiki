"""目的駆動 end-to-end runner.

Phase 5c で導入. 自然言語の目的入力から始まり、構造化スキーマへの変換、
評価器の流用 or 新規生成、ナレッジ層の読み込み、エージェント実行、
自動検証までを 1 ステップで通す.

Phase 7e-6 (2026-06-19) で `use_compose` フラグを追加. True のとき
`policy.compose.run_compose` を補助起動して AgentSquare 探索結果 (selected_modules,
search_score) を MLflow にロギングする. variant 実行は従来どおりで paired_diff の意味は変わらない.

設計: docs/experiments/phase5c_design.md §1.1 / phase7e_design.md §5
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mlflow

from tsumiki.data.clauses import CleanClause
from tsumiki.data.synthesis import ChatFn, SynthesisConfig
from tsumiki.goal.generator import generate_evaluator
from tsumiki.goal.lookup import search
from tsumiki.goal.parser import parse_goal
from tsumiki.goal.specs import EvaluatorSpec, TaskSpec
from tsumiki.goal.store import evaluator_dir
from tsumiki.goal.store import save as save_evaluator
from tsumiki.goal.verifier import load_evaluator_from_path, verify
from tsumiki.knowledge.loader import load_ng_patterns_auto
from tsumiki.llm.client import LLMSettings
from tsumiki.runner.phase2 import _build_synth_only_samples, run_phase2_variant


@dataclass(frozen=True)
class E2EConfig:
    """end-to-end 実行の入力一式."""

    goal: str
    clean_clauses: tuple[CleanClause, ...]
    seed: int
    n_synth_per_pattern: int
    runtime_model: str  # synth/modifier/detector で使うモデル名
    evaluator_root: Path  # eval/generated/ ルート
    parser_chat_fn: ChatFn  # 目的 → TaskSpec
    generator_chat_fn: ChatFn  # TaskSpec → EvaluatorSpec
    runtime_chat_fn: ChatFn  # detector / modifier 用
    mlflow_experiment: str
    outcomes_dir: Path | None
    auto_approve_eval: bool
    generated_at: str
    approved_by: str
    modifier_reuse_prompt_version: str
    modifier_zerobase_prompt_version: str
    detector_prompt_version: str
    knowledge_path: Path | None = None  # 明示指定. None なら TaskSpec から解決
    # Phase 7e-6: policy.compose 補助起動. use_compose=True のとき
    # AgentSquare 探索を起動して選択モジュールを MLflow にロギングする.
    # variant 実行は従来どおりで paired_diff の意味は変わらない (補助情報モード).
    use_compose: bool = False
    compose_max_depth: int = 3
    # use_compose=True のとき必須. evolution の JsonChatFn として渡す.
    # tsumiki.data.synthesis.make_openai_json_chat_fn で構築.
    compose_json_chat_fn: Callable[[list[dict[str, str]]], dict[str, Any]] | None = None
    # use_compose=True のとき必須. ComposeConfig.llm_settings に渡す.
    llm_settings: LLMSettings | None = None


@dataclass(frozen=True)
class E2EResult:
    task_spec: TaskSpec
    evaluator_spec: EvaluatorSpec
    evaluator_dir: Path
    reused_existing_evaluator: bool
    reuse_metrics: dict
    zerobase_metrics: dict
    paired_diff: float
    # Phase 7e-6: compose 補助起動の結果 (use_compose=False では None).
    compose_selected_modules: dict[str, str] | None = None
    compose_search_score: float | None = None


def run_e2e(cfg: E2EConfig) -> E2EResult:
    """end-to-end を実行する.

    フロー (設計 §1.1):
      1. parser で目的 → TaskSpec
      2. lookup で流用候補検索. 1 件以上あれば exact_match を採用
      3. 無ければ generator で新規生成 → verifier で test_cases を通過させる
      4. auto_approve_eval=True なら自動承認、False は ValueError
      5. store.save() で eval/generated/<domain>/<task_class>/<id>/ に保存
      6. Knowledge 層を Agent Skills or YAML で読み込み
      7. synth → reuse + zerobase 実行 (Phase 2 runner を再利用)
      8. 動的ロードした evaluate() で集約、paired diff を返す
    """
    print(f"[e2e] goal: {cfg.goal!r}")
    text_parser_fn = _to_text_chat_fn(cfg.parser_chat_fn)
    text_generator_fn = _to_text_chat_fn(cfg.generator_chat_fn)
    ts = parse_goal(cfg.goal, text_parser_fn)
    print(
        f"[e2e] task_spec: domain={ts.domain} task_class={ts.task_class} "
        f"inputs={[r.name for r in ts.input_roles]} outputs={[o.name for o in ts.outputs]}"
    )

    candidates = search(cfg.evaluator_root, ts)
    if candidates:
        spec = candidates[0].spec
        eval_dir = evaluator_dir(cfg.evaluator_root, spec)
        reused = True
        print(f"[e2e] reusing evaluator: {spec.id} (from {eval_dir})")
    else:
        spec = generate_evaluator(
            ts,
            text_generator_fn,
            generated_at=cfg.generated_at,
            approved_by=cfg.approved_by,
        )
        verification = verify(spec)
        if not verification.passed:
            raise ValueError(
                f"generated evaluator failed verify: error={verification.error} "
                f"failures={verification.failures}"
            )
        if not cfg.auto_approve_eval:
            raise NotImplementedError(
                "interactive evaluator approval not implemented; pass auto_approve_eval=True"
            )
        eval_dir = save_evaluator(cfg.evaluator_root, spec)
        reused = False
        print(f"[e2e] saved new evaluator: {spec.id} (to {eval_dir})")

    # Knowledge 層
    knowledge_path = cfg.knowledge_path
    if knowledge_path is None:
        if ts.knowledge.catalog_path is None:
            raise ValueError(
                "no knowledge path provided and TaskSpec.knowledge.catalog_path is null"
            )
        knowledge_path = Path(ts.knowledge.catalog_path)
    ng_book = load_ng_patterns_auto(knowledge_path)
    print(
        f"[e2e] knowledge loaded: version={ng_book.version} patterns={len(ng_book.patterns)}"
    )

    # synth + reuse + zerobase
    synth_cfg = SynthesisConfig(
        model=cfg.runtime_model, seed=cfg.seed, temperature=0.0
    )
    t_synth = time.monotonic()
    samples = _build_synth_only_samples(
        cfg.clean_clauses,
        ng_book.patterns,
        synth_cfg,
        n_synth_per_pattern=cfg.n_synth_per_pattern,
        synth_chat_fn=cfg.runtime_chat_fn,
        seed=cfg.seed,
    )
    print(
        f"[e2e] synth: {len(samples)} samples in {time.monotonic() - t_synth:.1f}s"
    )

    mlflow.set_experiment(cfg.mlflow_experiment)
    evaluate_fn = load_evaluator_from_path(eval_dir / "evaluator.py")
    metrics: dict[str, dict] = {}
    for variant_name, prompt_ver in (
        ("reuse", cfg.modifier_reuse_prompt_version),
        ("zerobase", cfg.modifier_zerobase_prompt_version),
    ):
        print(f"[e2e] --- variant={variant_name} prompt={prompt_ver} ---")
        outcomes_path: Path | None = None
        if cfg.outcomes_dir is not None:
            outcomes_path = cfg.outcomes_dir / f"{variant_name}_seed{cfg.seed}.jsonl"
        outcome = run_phase2_variant(
            variant_name=variant_name,
            samples=samples,
            ng_book=ng_book,
            modifier_chat_fn=cfg.runtime_chat_fn,
            detector_chat_fn=cfg.runtime_chat_fn,
            modifier_prompt_version=prompt_ver,
            detector_prompt_version=cfg.detector_prompt_version,
            run_params_extra={
                "seed": cfg.seed,
                "phase": "phase5c_e2e",
                "model": cfg.runtime_model,
                "n_synth_per_pattern": cfg.n_synth_per_pattern,
                "evaluator_id": spec.id,
                "reused_evaluator": reused,
            },
            run_name=(
                f"e2e_{variant_name}_s{cfg.seed}_{time.strftime('%Y%m%d_%H%M%S')}"
            ),
            outcomes_jsonl_path=outcomes_path,
        )
        if outcomes_path is not None and outcomes_path.is_file():
            outcomes = _load_outcomes(outcomes_path)
            metrics[variant_name] = evaluate_fn(outcomes)
            sr = float(metrics[variant_name].get("modification_success_rate", 0.0))
            nt = float(metrics[variant_name].get("negative_transfer_rate", 0.0))
            print(
                f"[e2e] {variant_name}: n_samples={outcome.n_samples} "
                f"success_rate={sr:.3f} negative_transfer={nt:.3f}"
            )
        else:
            metrics[variant_name] = {}

    reuse_sr = float(metrics.get("reuse", {}).get("modification_success_rate", 0.0))
    zerobase_sr = float(
        metrics.get("zerobase", {}).get("modification_success_rate", 0.0)
    )
    paired_diff = reuse_sr - zerobase_sr
    print(f"[e2e] paired diff = {paired_diff:+.3f}")

    # Phase 7e-6: policy.compose 補助起動.
    compose_selected: dict[str, str] | None = None
    compose_score: float | None = None
    if cfg.use_compose:
        compose_selected, compose_score = _run_compose_auxiliary(
            cfg=cfg, ts=ts, spec=spec, ng_book=ng_book, reuse_sr=reuse_sr
        )

    return E2EResult(
        task_spec=ts,
        evaluator_spec=spec,
        evaluator_dir=eval_dir,
        reused_existing_evaluator=reused,
        reuse_metrics=metrics.get("reuse", {}),
        zerobase_metrics=metrics.get("zerobase", {}),
        paired_diff=paired_diff,
        compose_selected_modules=compose_selected,
        compose_search_score=compose_score,
    )


def _run_compose_auxiliary(
    *,
    cfg: E2EConfig,
    ts: TaskSpec,
    spec: EvaluatorSpec,
    ng_book,  # noqa: ANN001
    reuse_sr: float,
) -> tuple[dict[str, str], float]:
    """`policy.compose.run_compose` を補助起動して探索結果を MLflow にロギングする.

    Phase 7e-6 では benchmark_fn は trivial (常に reuse_sr を返す). compose の
    動作確証 (gate 通過 + AgentSquare 探索ループが回る) を smoke レベルで確認するため.
    本格的な探索評価は Phase 9+ で benchmark_fn を `agentsquare.*` 合成 chat_fn 経由
    で構築した上で実走させる.
    """
    from tsumiki.policy.compose import ComposeConfig, run_compose

    if cfg.llm_settings is None:
        raise ValueError("use_compose=True requires E2EConfig.llm_settings")
    if cfg.compose_json_chat_fn is None:
        raise ValueError("use_compose=True requires E2EConfig.compose_json_chat_fn")

    text_chat_fn = _to_text_chat_fn(cfg.runtime_chat_fn)

    def _benchmark_fn(_agent: dict[str, str]) -> float:
        # 補助情報モード: variant 実行は既に終わっているため reuse_sr を返す.
        # Phase 9+ で本物の合成 chat_fn 構築 + 評価を行う想定.
        return reuse_sr

    compose_cfg = ComposeConfig(
        task_spec=ts,
        evaluator_spec=spec,
        knowledge=ng_book,
        llm_settings=cfg.llm_settings,
        chat_fn=text_chat_fn,
        json_chat_fn=cfg.compose_json_chat_fn,
        benchmark_fn=_benchmark_fn,
        max_search_depth=cfg.compose_max_depth,
        seed=cfg.seed,
    )
    result = run_compose(compose_cfg)
    print(
        f"[compose] selected={result.selected_modules} score={result.search_score:.3f} "
        f"depth={cfg.compose_max_depth}"
    )
    # active run が無いと mlflow.log_dict が自動で start_run() を呼んで
    # 他 test の run と衝突する. active_run() ガードで明示的にスキップする.
    if mlflow.active_run() is not None:
        try:
            mlflow.log_dict(result.selected_modules, "compose_selected_modules.json")
            mlflow.log_metric("compose_search_score", float(result.search_score))
        except Exception as e:  # noqa: BLE001
            print(f"[compose] mlflow log skipped: {e}")
    return dict(result.selected_modules), float(result.search_score)


def _to_text_chat_fn(rich_chat_fn: ChatFn) -> Callable[[str], str]:
    """tsumiki.data.synthesis.ChatFn (ChatResult を返す) を str -> str にアダプトする.

    goal/parser.py と goal/generator.py は token 集計を不要とするため、
    content だけ取り出す薄いラッパ.
    """

    def fn(prompt: str) -> str:
        return rich_chat_fn(prompt).content

    return fn


def _load_outcomes(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
