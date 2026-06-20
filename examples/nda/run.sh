#!/usr/bin/env bash
# tsumiki examples/nda — NDA リファレンス実装の E2E 実行.
# 同一 `src/tsumiki/runner/e2e.py` を ISO27001 と共有 (計画書 §10.3 ドメイン非依存性).
set -euo pipefail

cd "$(dirname "$0")/../.."

: "${LLM_PROVIDER:=openai_compatible}"
: "${LLM_BASE_URL:=http://localhost:11434/v1}"
: "${LLM_API_KEY:=ollama}"
: "${LLM_MODEL:=qwen25-14b-ctx8k}"
export LLM_PROVIDER LLM_BASE_URL LLM_API_KEY LLM_MODEL

uv run python experiments/run_phase5c_dryrun.py \
  --goal "NDA をチェックして問題条項を是正したい" \
  --knowledge-path examples/nda/knowledge \
  --clean-jsonl examples/nda/clean_clauses.jsonl \
  --experiment examples_nda \
  --outcomes-dir examples/nda/outcomes \
  --evaluator-root src/tsumiki/eval/generated \
  --baseline-paired-diff 0.261 \
  --baseline-label "Phase 5c NDA" \
  --seed 42 \
  "$@"
