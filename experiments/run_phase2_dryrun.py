"""Phase 2 対照実験 (再利用 vs ゼロベース) Runner.

T1 (検出) は Phase 1 確定ベースライン (P2 = v0.3.0 + ng_patterns v0.1.0) を使う。
T2 (修正) は 2 つの variant を比較する:
  - reuse  : T1 と同じ NG パターン辞書を使う知識層再利用
  - zerobase: 辞書を使わない素朴な「不適切な部分を修正」プロンプト

使い方:
    # 前提: .env で LLM_BASE_URL / LLM_API_KEY / LLM_MODEL を設定
    uv run python experiments/run_phase2_dryrun.py [--seeds 42 43 44]

CLI 引数は .env の値を上書きする。
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import mlflow
from dotenv import load_dotenv

from tsumiki.baseline import (
    MODIFICATION_PROMPT_VERSION_LATEST_REUSE,
    MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE,
)
from tsumiki.data.clauses import CleanClause
from tsumiki.data.synthesis import SynthesisConfig, make_openai_chat_fn
from tsumiki.exp import setup_tracking
from tsumiki.knowledge import load_ng_patterns
from tsumiki.knowledge.loader import load_ng_patterns_auto
from tsumiki.llm import LLMSettings, build_client
from tsumiki.runner.phase2 import (
    _build_synth_only_samples,
    run_phase2_variant,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLEAN_JSONL = PROJECT_ROOT / "data" / "processed" / "nda_clean_clauses.jsonl"

# .env を最優先で読み込む（CLI 引数は後段で上書き）
load_dotenv(PROJECT_ROOT / ".env", override=False)


def load_clean_clauses(path: Path) -> list[CleanClause]:
    clauses: list[CleanClause] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            clauses.append(CleanClause(**d))
    return clauses


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    default_provider = os.environ.get("LLM_PROVIDER", "openai_compatible")
    if default_provider == "azure_openai":
        default_model = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
        default_base_url = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        default_api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    else:
        default_model = os.environ.get(
            "LLM_MODEL", "hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M"
        )
        default_base_url = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
        default_api_key = os.environ.get("LLM_API_KEY", "ollama")
    p.add_argument(
        "--model",
        default=default_model,
        help="モデルタグ（azure では deployment 名）。CLI 指定は .env を上書き",
    )
    p.add_argument("--base-url", default=default_base_url)
    p.add_argument("--api-key", default=default_api_key)
    p.add_argument("--experiment", default="phase2_reuse_vs_zerobase")
    p.add_argument("--seeds", type=int, nargs="+", default=[42])
    p.add_argument("--n-synth-per-pattern", type=int, default=3)
    p.add_argument("--detector-prompt-version", default="v0.3.0")
    p.add_argument(
        "--outcomes-dir",
        type=Path,
        default=None,
        help="指定すると個別 outcome を <dir>/<variant>_seed<seed>.jsonl に保存し MLflow artifact に添付する",
    )
    p.add_argument(
        "--reuse-prompt-version",
        default=MODIFICATION_PROMPT_VERSION_LATEST_REUSE,
        help="reuse variant の修正プロンプトバージョン（頑健性試験用に v0.1.1 等を指定）",
    )
    p.add_argument(
        "--zerobase-prompt-version",
        default=MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE,
        help="zerobase variant の修正プロンプトバージョン（頑健性試験用に v0.1.1 等を指定）",
    )
    p.add_argument(
        "--variant-suffix",
        default="",
        help="MLflow run_name に追加する suffix（例: '_paraphrase' で v0.1.0 走行と区別）",
    )
    p.add_argument(
        "--ng-patterns-path",
        type=Path,
        default=None,
        help="代替の NG パターン辞書 YAML パス（Phase 4 ハイブリッド辞書 v0.4.0 等を指定）",
    )
    p.add_argument(
        "--num-ctx",
        type=int,
        default=None,
        help="ローカル ollama の context size（クラウド辞書で prompt が長い場合 8192 等を指定）",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not CLEAN_JSONL.is_file():
        print(f"[error] {CLEAN_JSONL.relative_to(PROJECT_ROOT)} が存在しません.")
        return 1

    clauses = load_clean_clauses(CLEAN_JSONL)
    if args.ng_patterns_path is not None:
        book = load_ng_patterns_auto(args.ng_patterns_path)
        kind = "skills-dir" if args.ng_patterns_path.is_dir() else "yaml"
        print(
            f"[setup] NG patterns loaded from {args.ng_patterns_path} "
            f"(version={book.version}, format={kind})"
        )
    else:
        book = load_ng_patterns("nda")
        print(f"[setup] NG patterns loaded from default (version={book.version})")
    print(f"[setup] clean clauses = {len(clauses)}, NG patterns = {len(book.patterns)}")
    provider = os.environ.get("LLM_PROVIDER", "openai_compatible")
    print(f"[setup] provider={provider} base_url={args.base_url} model={args.model}")
    print(f"[setup] seeds = {args.seeds}")
    print(f"[setup] n_synth_per_pattern = {args.n_synth_per_pattern}")

    if provider == "azure_openai":
        settings = LLMSettings(
            provider="azure_openai",
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            temperature=0.0,
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", ""),
        )
    else:
        settings = LLMSettings(
            provider="openai_compatible",
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            temperature=0.0,
        )
    client = build_client(settings)
    setup_tracking()
    mlflow.set_experiment(args.experiment)

    for seed in args.seeds:
        synth_cfg = SynthesisConfig(model=args.model, seed=seed, temperature=0.0)
        chat_fn = make_openai_chat_fn(
            client, args.model, temperature=0.0, seed=seed, num_ctx=args.num_ctx
        )

        print(f"\n========== seed={seed} ==========")
        t_synth = time.monotonic()
        samples = _build_synth_only_samples(
            clauses,
            book.patterns,
            synth_cfg,
            n_synth_per_pattern=args.n_synth_per_pattern,
            synth_chat_fn=chat_fn,
            seed=seed,
        )
        elapsed_synth = time.monotonic() - t_synth
        print(f"[synth] generated {len(samples)} samples in {elapsed_synth:.1f}s")

        for variant_name, prompt_ver in (
            ("reuse", args.reuse_prompt_version),
            ("zerobase", args.zerobase_prompt_version),
        ):
            print(f"\n--- variant={variant_name} prompt={prompt_ver} ---")
            t_v = time.monotonic()
            outcomes_path = None
            if args.outcomes_dir is not None:
                outcomes_path = (
                    args.outcomes_dir
                    / f"{variant_name}{args.variant_suffix}_seed{seed}.jsonl"
                )
            outcome = run_phase2_variant(
                variant_name=f"{variant_name}{args.variant_suffix}",
                samples=samples,
                ng_book=book,
                modifier_chat_fn=chat_fn,
                detector_chat_fn=chat_fn,
                modifier_prompt_version=prompt_ver,
                detector_prompt_version=args.detector_prompt_version,
                run_params_extra={
                    "seed": seed,
                    "model": args.model,
                    "phase": "phase2_dryrun",
                    "n_synth_per_pattern": args.n_synth_per_pattern,
                },
                run_name=f"{variant_name}{args.variant_suffix}_s{seed}_{time.strftime('%Y%m%d_%H%M%S')}",
                outcomes_jsonl_path=outcomes_path,
            )
            elapsed_v = time.monotonic() - t_v
            r = outcome.report
            print(
                f"[{variant_name}] samples={r.n_samples}  "
                f"success_rate={r.modification_success_rate:.3f}  "
                f"negative_transfer={r.negative_transfer_rate:.3f}  "
                f"elapsed={elapsed_v:.1f}s"
            )
            for pid in sorted(r.per_pattern_support):
                print(
                    f"  {pid:35s} support={r.per_pattern_support[pid]} "
                    f"success={r.per_pattern_success[pid]:.2f}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
