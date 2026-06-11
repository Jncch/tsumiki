"""Phase 1 軽量試走スクリプト.

中小企業庁 NDA 雛形から作った CleanClause と NG パターン辞書 (v0.1.0) で、
qwen2.5 7B Instruct を合成器・ベースライン検出器の両方に使い、
合成→層化分割→ベースライン予測→評価→MLflow 記録までを 1 コマンドで回す。

使い方:
    # 前提: .env で LLM_BASE_URL / LLM_API_KEY / LLM_MODEL を設定
    #       （.env.example をコピーして編集）
    # 前提: data/processed/nda_clean_clauses.jsonl が生成済
    uv run python experiments/run_phase1_dryrun.py

CLI 引数は .env の値を上書きする（テスト・即興走行用）。
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import mlflow
from dotenv import load_dotenv

from tsumiki.data.clauses import CleanClause
from tsumiki.data.synthesis import SynthesisConfig, make_openai_chat_fn
from tsumiki.eval.split import SplitConfig
from tsumiki.exp import setup_tracking
from tsumiki.knowledge import load_ng_patterns
from tsumiki.llm import LLMSettings, build_client
from tsumiki.runner import run_phase1

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
    # 既定値は .env 経由（azure_openai の場合は AZURE_OPENAI_DEPLOYMENT が --model になる）
    default_provider = os.environ.get("LLM_PROVIDER", "openai_compatible")
    if default_provider == "azure_openai":
        default_model = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
        default_base_url = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    else:
        default_model = os.environ.get(
            "LLM_MODEL", "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"
        )
        default_base_url = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
    p.add_argument(
        "--model",
        default=default_model,
        help="モデルタグ（azure では deployment 名）。CLI 指定は .env を上書き",
    )
    p.add_argument(
        "--base-url",
        default=default_base_url,
        help="OpenAI 互換エンドポイント（azure では endpoint）。CLI 指定は .env を上書き",
    )
    p.add_argument(
        "--api-key",
        default=os.environ.get(
            "AZURE_OPENAI_API_KEY" if default_provider == "azure_openai" else "LLM_API_KEY",
            "ollama",
        ),
        help="API キー（.env *_API_KEY を上書き、ローカル ollama は 'ollama' で OK）",
    )
    p.add_argument(
        "--quant-tag", default="Q4_K_M", help="MLflow に記録する量子化タグ"
    )
    p.add_argument(
        "--experiment",
        default="phase1_dryrun",
        help="MLflow experiment name",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-clean", type=int, default=10)
    p.add_argument("--n-synth-per-pattern", type=int, default=2)
    p.add_argument("--train-ratio", type=float, default=0.6)
    p.add_argument("--val-ratio", type=float, default=0.2)
    p.add_argument(
        "--baseline-prompt-version",
        default="v0.1.0",
        help="ベースライン検出器のプロンプトバージョン (v0.1.0 / v0.2.0 等)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not CLEAN_JSONL.is_file():
        print(f"[error] {CLEAN_JSONL.relative_to(PROJECT_ROOT)} が存在しません.")
        print("  先に: uv run python experiments/build_clean_clauses.py")
        return 1

    clauses = load_clean_clauses(CLEAN_JSONL)
    book = load_ng_patterns("nda")
    print(f"[setup] clean clauses = {len(clauses)}, NG patterns = {len(book.patterns)}")
    provider = os.environ.get("LLM_PROVIDER", "openai_compatible")
    print(f"[setup] provider={provider} base_url={args.base_url} model={args.model}")

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
    chat_fn = make_openai_chat_fn(client, args.model, temperature=0.0, seed=args.seed)

    setup_tracking()
    mlflow.set_experiment(args.experiment)

    synth_cfg = SynthesisConfig(model=args.model, seed=args.seed, temperature=0.0)
    split_cfg = SplitConfig(
        seed=args.seed, train_ratio=args.train_ratio, val_ratio=args.val_ratio
    )

    t0 = time.monotonic()
    outcome = run_phase1(
        clean_clauses=clauses,
        ng_book=book,
        synth_config=synth_cfg,
        split_config=split_cfg,
        n_synth_per_pattern=args.n_synth_per_pattern,
        n_clean=args.n_clean,
        synth_chat_fn=chat_fn,
        baseline_chat_fn=chat_fn,
        baseline_model=args.model,
        baseline_quant_tag=args.quant_tag,
        baseline_prompt_version=args.baseline_prompt_version,
        run_name=f"dryrun_{time.strftime('%Y%m%d_%H%M%S')}",
    )
    elapsed = time.monotonic() - t0

    print(f"\n=== outcome (elapsed {elapsed:.1f}s) ===")
    print(f"train={outcome.n_train}  val={outcome.n_val}  test={outcome.n_test}")
    for split_name, report in (("VAL", outcome.val_report), ("TEST", outcome.test_report)):
        print(
            f"{split_name:4s} support={report.total_support}  "
            f"macro_recall={report.macro_recall:.3f}  "
            f"macro_precision={report.macro_precision:.3f}  "
            f"macro_F{report.beta:.0f}={report.macro_fbeta:.3f}"
        )
    print("\n=== per-pattern (TEST、support>0 のみ) ===")
    for m in outcome.test_report.per_pattern:
        if m.support > 0:
            print(
                f"  {m.pattern_id:34s} support={m.support} tp={m.tp} fp={m.fp} fn={m.fn}  "
                f"recall={m.recall:.2f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
