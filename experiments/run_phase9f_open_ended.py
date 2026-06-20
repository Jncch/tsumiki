"""Phase 9f (2026-06-21): 開放タスク試走スクリプト.

dialog_seed.yaml を replay → EvaluatorDraft 構築 → _run_open_ended_e2e 実行.
4 ドメイン (marketing_post / meeting_summary / spec_to_tests / campaign_proposal)
共通で使う.

Usage:
    uv run python experiments/run_phase9f_open_ended.py \\
        --example examples/marketing_post \\
        --experiment phase9f_marketing_post
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from tsumiki.data.synthesis import make_openai_chat_fn, make_openai_json_chat_fn
from tsumiki.goal.dialog import (
    DialogConfig,
    DialogState,
    stage1_clarify_goal,
    stage2_select_dimensions,
    stage3_draft_evaluator,
)
from tsumiki.goal.specs import KnowledgeSource, OutputSchema, TaskSpec
from tsumiki.knowledge.schemas.eval_dimensions import EvalDimension
from tsumiki.llm.client import LLMSettings, build_client
from tsumiki.runner.e2e import E2EConfig, run_e2e


def _scripted_input_from_seed(seed: dict[str, Any]):
    """dialog_seed の dict から scripted input_fn を作る.

    答えは Q ID をキーに seed から引く. キーが無ければ空文字を返す.
    """
    used: set[str] = set()

    def fn(qid: str) -> str:
        used.add(qid)
        # `__after_suggest` / `__no_suggest` のサフィックスは元 Q ID で引く
        base = qid.split("__")[0] if "__" in qid else qid
        if qid in seed:
            return str(seed[qid])
        if base in seed:
            return str(seed[base])
        return ""

    return fn, used


def _silent_output(_msg: str) -> None:
    print(_msg)


def _load_knowledge_text(catalog_path: str) -> str | None:
    """Agent Skills 形式 SKILL.md を読み込んで knowledge_text として返す.

    存在しなければ None.
    """
    p = Path(catalog_path)
    if not p.is_dir():
        return None
    skill_files = sorted(p.glob("**/*.md"))
    if not skill_files:
        return None
    chunks = []
    for f in skill_files:
        chunks.append(f"# === {f.relative_to(p)} ===\n{f.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)


def _build_task_spec_from_goal_yaml(goal_data: dict[str, Any]) -> TaskSpec:
    """goal.yaml を TaskSpec dataclass にマップ."""
    from tsumiki.goal.specs import InputRole

    input_roles = tuple(
        InputRole(
            name=r["name"],
            formats=tuple(r.get("formats", ["txt"])),
            role=r["role"],
            description=r.get("description", ""),
        )
        for r in goal_data.get("input_roles", []) or []
    )
    outputs = tuple(
        OutputSchema(
            name=o["name"],
            schema_id=o["schema_id"],
            description=o.get("description", ""),
        )
        for o in goal_data.get("outputs", []) or []
    )
    k = goal_data.get("knowledge", {}) or {}
    knowledge = KnowledgeSource(
        source_type=k.get("source_type", "existing"),
        catalog_path=k.get("catalog_path"),
    )
    return TaskSpec(
        task_class=goal_data["task_class"],
        domain=goal_data["domain"],
        input_roles=input_roles,
        knowledge=knowledge,
        outputs=outputs,
        raw_goal=goal_data["raw_goal"],
        output_kind=goal_data["output_kind"],
        input_modality=goal_data["input_modality"],
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--example", required=True, type=Path, help="examples/<domain>/ ディレクトリ")
    ap.add_argument("--experiment", required=True, help="MLflow experiment 名")
    ap.add_argument("--sample-count", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outcomes-dir", type=Path, default=None)
    args = ap.parse_args()

    example_dir: Path = args.example
    if not example_dir.is_dir():
        print(f"[error] example dir not found: {example_dir}", file=sys.stderr)
        return 2

    goal_yaml = example_dir / "goal.yaml"
    seed_yaml = example_dir / "dialog_seed.yaml"
    if not goal_yaml.is_file() or not seed_yaml.is_file():
        print(f"[error] goal.yaml or dialog_seed.yaml missing under {example_dir}", file=sys.stderr)
        return 2

    goal_data = yaml.safe_load(goal_yaml.read_text(encoding="utf-8"))
    seed_data = yaml.safe_load(seed_yaml.read_text(encoding="utf-8"))

    # 1) dialog seed から EvaluatorDraft を組み立てる
    print(f"[phase9f] replaying dialog from {seed_yaml}")
    input_fn, _ = _scripted_input_from_seed(seed_data)
    dialog_cfg = DialogConfig(log_dir=example_dir / "outcomes" / "dialog_logs")
    state = DialogState()
    state = stage1_clarify_goal(state, dialog_cfg, None, input_fn, _silent_output)
    state = stage2_select_dimensions(state, dialog_cfg, input_fn, _silent_output)
    state = stage3_draft_evaluator(state, dialog_cfg, None, input_fn, _silent_output)
    if state.eval_spec_draft is None:
        print("[error] eval_spec_draft was not confirmed; check dialog_seed.yaml", file=sys.stderr)
        return 3
    draft = state.eval_spec_draft
    print(f"[phase9f] draft built: dimensions={[d.dimension_id for d in draft.dimensions]} strictness={draft.strictness}")

    # 2) goal.yaml から TaskSpec を再構築
    task_spec = _build_task_spec_from_goal_yaml(goal_data)

    # 3) knowledge text を読み込む
    knowledge_text = None
    if task_spec.knowledge.catalog_path:
        knowledge_text = _load_knowledge_text(task_spec.knowledge.catalog_path)
        if knowledge_text:
            print(f"[phase9f] knowledge loaded: {len(knowledge_text)} chars")
        else:
            print(f"[phase9f] knowledge skill not found at {task_spec.knowledge.catalog_path}")

    # 4) LLM プロバイダ
    llm = LLMSettings.from_env()
    print(f"[llm] provider={llm.provider} model={llm.model}")
    client = build_client(llm)
    text_chat_fn = make_openai_chat_fn(client, llm)
    json_chat_fn = make_openai_json_chat_fn(client, llm)

    # 5) E2EConfig 組み立て (open-ended パスのみ使用)
    cfg = E2EConfig(
        goal=task_spec.raw_goal,
        clean_clauses=(),
        seed=args.seed,
        n_synth_per_pattern=0,
        runtime_model=llm.model,
        evaluator_root=Path("src/tsumiki/eval/generated"),
        # 開放タスクでは parser/generator は使われないが必須なので no-op を渡す.
        parser_chat_fn=text_chat_fn,
        generator_chat_fn=text_chat_fn,
        runtime_chat_fn=text_chat_fn,
        mlflow_experiment=args.experiment,
        outcomes_dir=args.outcomes_dir,
        auto_approve_eval=True,
        generated_at="2026-06-21",
        approved_by=f"phase9f_seed_{task_spec.domain}",
        modifier_reuse_prompt_version="reuse.v0.1.0",
        modifier_zerobase_prompt_version="zerobase.v0.1.0",
        detector_prompt_version="detector.v0.1.0",
        evaluator_draft=draft,
        open_ended_sample_count=args.sample_count,
        open_ended_json_chat_fn=json_chat_fn,
        open_ended_knowledge_text=knowledge_text,
    )

    # 6) 実走
    # task_spec を parser を介さず E2EConfig.goal から再構築させるためには
    # parse_goal が同じ TaskSpec を返す保証が無い. 開放タスク経路に直接渡す.
    from tsumiki.runner.e2e import _run_open_ended_e2e
    result = _run_open_ended_e2e(cfg, task_spec)

    print("\n========== Phase 9f Open-Ended Summary ==========")
    print(f"  domain:           {result.task_spec.domain}")
    print(f"  task_class:       {result.task_spec.task_class}")
    print(f"  output_kind:      {result.task_spec.output_kind}")
    print(f"  input_modality:   {result.task_spec.input_modality}")
    print(f"  reuse_score:      {result.reuse_score:.3f}")
    print(f"  zerobase_score:   {result.zerobase_score:.3f}")
    print(f"  score_diff:       {result.score_diff:+.3f}")
    print(f"  sample_count:     {args.sample_count}")
    print(f"  reuse_samples:    {len(result.reuse_samples or ())}")
    print(f"  zerobase_samples: {len(result.zerobase_samples or ())}")

    # outcomes に詳細を書き出す
    if args.outcomes_dir is not None:
        args.outcomes_dir.mkdir(parents=True, exist_ok=True)
        outpath = args.outcomes_dir / f"phase9f_{result.task_spec.domain}_seed{args.seed}.json"
        outpath.write_text(
            json.dumps(
                {
                    "domain": result.task_spec.domain,
                    "reuse_score": result.reuse_score,
                    "zerobase_score": result.zerobase_score,
                    "score_diff": result.score_diff,
                    "reuse_samples": list(result.reuse_samples or ()),
                    "zerobase_samples": list(result.zerobase_samples or ()),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  outcomes:         {outpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
