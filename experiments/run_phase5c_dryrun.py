"""Phase 5c 目的駆動 end-to-end 試走スクリプト.

NDA で run_e2e を 1 回実行し、自然言語目的 → TaskSpec → 評価器（流用 or 生成）
→ Knowledge 読み込み → reuse + zerobase 実行 → paired diff 算出まで一気通貫で
動くことを確認する.

設計: docs/experiments/phase5c_design.md §5.1, §5.2
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from tsumiki.baseline import (
    MODIFICATION_PROMPT_VERSION_LATEST_REUSE,
    MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE,
)
from tsumiki.data.clauses import CleanClause
from tsumiki.data.synthesis import make_openai_chat_fn, make_openai_json_chat_fn
from tsumiki.exp import setup_tracking
from tsumiki.llm import LLMSettings, build_client
from tsumiki.runner.e2e import E2EConfig, run_e2e

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLEAN_JSONL = PROJECT_ROOT / "data" / "processed" / "nda_clean_clauses.jsonl"
DEFAULT_EVAL_ROOT = PROJECT_ROOT / "src" / "tsumiki" / "eval" / "generated"
DEFAULT_KNOWLEDGE = (
    PROJECT_ROOT / "src" / "tsumiki" / "knowledge" / "skills" / "nda" / "ng_patterns"
)
DEFAULT_OUTCOMES_DIR = PROJECT_ROOT / "docs" / "experiments" / "phase5c_outcomes"

load_dotenv(PROJECT_ROOT / ".env", override=False)


def load_clean_clauses(path: Path) -> list[CleanClause]:
    out: list[CleanClause] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out.append(CleanClause(**d))
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--goal",
        default="NDA をレビューして NG 条項を直したい",
        help="自然言語の目的入力",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-synth-per-pattern", type=int, default=5)
    p.add_argument(
        "--clean-jsonl",
        type=Path,
        default=DEFAULT_CLEAN_JSONL,
        help=(
            "clean clauses の JSONL パス. "
            "NDA: data/processed/nda_clean_clauses.jsonl, "
            "ISO27001: data/processed/iso27001_clean_clauses.jsonl"
        ),
    )
    p.add_argument(
        "--evaluator-root",
        type=Path,
        default=DEFAULT_EVAL_ROOT,
        help="流用蓄積ルート",
    )
    p.add_argument(
        "--knowledge-path",
        type=Path,
        default=DEFAULT_KNOWLEDGE,
        help="ナレッジカタログのパス. ディレクトリなら Agent Skills, ファイルなら YAML",
    )
    p.add_argument("--experiment", default="phase5c_e2e")
    p.add_argument("--outcomes-dir", type=Path, default=DEFAULT_OUTCOMES_DIR)
    p.add_argument(
        "--auto-approve-eval",
        action="store_true",
        default=True,
        help="Phase 5c 雛形では True 固定. 対話承認は Phase 6 以降",
    )
    p.add_argument("--approved-by", default="auto")
    p.add_argument("--generated-at", default="2026-06-19")

    # Phase 7-bonus-3 (2026-06-19): CLI 引数による上書きを復活.
    # 優先順位: CLI 引数 > .env / 環境変数 > デフォルト.
    # Azure / OpenAI 互換 / ollama を試走時に切り替えやすくする.
    p.add_argument(
        "--llm-provider",
        choices=["openai_compatible", "azure_openai"],
        default=None,
        help="LLM_PROVIDER を上書き. 未指定なら .env 値.",
    )
    p.add_argument(
        "--llm-base-url",
        default=None,
        help="LLM_BASE_URL (openai_compatible) または AZURE_OPENAI_ENDPOINT を上書き.",
    )
    p.add_argument(
        "--llm-api-key",
        default=None,
        help="LLM_API_KEY または AZURE_OPENAI_API_KEY を上書き.",
    )
    p.add_argument(
        "--llm-model",
        default=None,
        help="LLM_MODEL または AZURE_OPENAI_DEPLOYMENT を上書き.",
    )
    p.add_argument(
        "--llm-temperature",
        type=float,
        default=None,
        help="LLM_TEMPERATURE を上書き.",
    )
    p.add_argument(
        "--azure-api-version",
        default=None,
        help="AZURE_OPENAI_API_VERSION を上書き (azure_openai でのみ意味あり).",
    )
    p.add_argument("--num-ctx", type=int, default=8192)
    p.add_argument(
        "--reuse-prompt-version", default=MODIFICATION_PROMPT_VERSION_LATEST_REUSE
    )
    p.add_argument(
        "--zerobase-prompt-version",
        default=MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE,
    )
    p.add_argument("--detector-prompt-version", default="v0.3.0")
    p.add_argument(
        "--baseline-paired-diff",
        type=float,
        default=None,
        help=(
            "paired_diff の参照 baseline. 指定時のみ gate 表示する. "
            "NDA Phase 5c=+0.261, ISO27001 Phase 6=+0.029."
        ),
    )
    p.add_argument(
        "--baseline-label",
        default="baseline",
        help="baseline 表示ラベル (例: 'Phase 5c NDA')",
    )
    p.add_argument(
        "--gate-tolerance",
        type=float,
        default=0.05,
        help="paired_diff の許容誤差 (デフォルト 0.05)",
    )
    # Phase 7e-6: policy.compose 補助起動.
    p.add_argument(
        "--use-compose",
        action="store_true",
        help=(
            "AgentSquare 探索を policy.compose 経由で補助起動する. "
            "variant 実行は従来どおりで paired_diff の意味は変わらない."
        ),
    )
    p.add_argument(
        "--compose-max-depth",
        type=int,
        default=1,
        help="compose 探索ループの iteration 数 (デフォルト 1, smoke 用).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    clean_jsonl = args.clean_jsonl.resolve()
    if not clean_jsonl.is_file():
        print(f"[error] {clean_jsonl} not found")
        return 1
    clauses = tuple(load_clean_clauses(clean_jsonl))
    print(f"[setup] clean_jsonl={clean_jsonl} clauses={len(clauses)}")

    # Phase 7-bonus-3: from_env_with_overrides() で CLI 引数 > .env > デフォルトの順で解決.
    settings = LLMSettings.from_env_with_overrides(
        provider=args.llm_provider,
        base_url=args.llm_base_url,
        api_key=args.llm_api_key,
        model=args.llm_model,
        temperature=args.llm_temperature,
        api_version=args.azure_api_version,
    )
    print(
        f"[llm] provider={settings.provider} model={settings.model} "
        f"temperature={settings.temperature}"
    )
    client = build_client(settings)
    # Phase 7d-4: num_ctx は ollama 拡張 (options.num_ctx). Azure / OpenAI / Anthropic
    # クラウド系に送ると `Unknown parameter: 'options'` で 400 になるため ollama 限定.
    effective_num_ctx = args.num_ctx if settings.is_ollama else None
    chat_fn = make_openai_chat_fn(
        client,
        settings.model,
        temperature=settings.temperature,
        seed=args.seed,
        num_ctx=effective_num_ctx,
    )
    setup_tracking()
    if args.outcomes_dir is not None:
        args.outcomes_dir.mkdir(parents=True, exist_ok=True)

    # Phase 7e-6: use_compose=True なら JSON 応答用 chat fn も用意する.
    compose_json_chat_fn = None
    if args.use_compose:
        compose_json_chat_fn = make_openai_json_chat_fn(
            client,
            settings.model,
            temperature=settings.temperature,
            seed=args.seed,
            num_ctx=effective_num_ctx,
        )

    cfg = E2EConfig(
        goal=args.goal,
        clean_clauses=clauses,
        seed=args.seed,
        n_synth_per_pattern=args.n_synth_per_pattern,
        runtime_model=settings.model,
        evaluator_root=args.evaluator_root,
        knowledge_path=args.knowledge_path,
        parser_chat_fn=chat_fn,
        generator_chat_fn=chat_fn,
        runtime_chat_fn=chat_fn,
        mlflow_experiment=args.experiment,
        outcomes_dir=args.outcomes_dir,
        auto_approve_eval=args.auto_approve_eval,
        generated_at=args.generated_at,
        approved_by=args.approved_by,
        modifier_reuse_prompt_version=args.reuse_prompt_version,
        modifier_zerobase_prompt_version=args.zerobase_prompt_version,
        detector_prompt_version=args.detector_prompt_version,
        use_compose=args.use_compose,
        compose_max_depth=args.compose_max_depth,
        compose_json_chat_fn=compose_json_chat_fn,
        llm_settings=settings if args.use_compose else None,
    )
    result = run_e2e(cfg)

    print("\n========== Phase 5c E2E Summary ==========")
    print(f"  goal:                  {args.goal!r}")
    print(f"  task_class:            {result.task_spec.task_class}")
    print(f"  domain:                {result.task_spec.domain}")
    print(f"  evaluator_id:          {result.evaluator_spec.id}")
    print(f"  reused_existing:       {result.reused_existing_evaluator}")
    reuse_sr = result.reuse_metrics.get("modification_success_rate")
    zerobase_sr = result.zerobase_metrics.get("modification_success_rate")
    print(f"  reuse success_rate:    {reuse_sr}")
    print(f"  zerobase success_rate: {zerobase_sr}")
    print(f"  paired_diff:           {result.paired_diff:+.3f}")
    if args.baseline_paired_diff is not None:
        print(
            f"  baseline ({args.baseline_label}):"
            f"{args.baseline_paired_diff:+.3f}"
        )
        gate = (
            "OK"
            if abs(result.paired_diff - args.baseline_paired_diff) <= args.gate_tolerance
            else "FAIL"
        )
        print(f"  gate (±{args.gate_tolerance:.2f}):          {gate}")
    if result.compose_selected_modules is not None:
        print(f"  compose selected:      {result.compose_selected_modules}")
        print(f"  compose score:         {result.compose_search_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
