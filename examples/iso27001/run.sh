#!/usr/bin/env bash
# tsumiki examples/iso27001 — ISO27001 監査チェックの E2E 実行.
# 同一 `src/tsumiki/runner/e2e.py` を NDA と共有 (計画書 §10.3 ドメイン非依存性).
set -euo pipefail

cd "$(dirname "$0")/../.."

: "${LLM_PROVIDER:=openai_compatible}"
: "${LLM_BASE_URL:=http://localhost:11434/v1}"
: "${LLM_API_KEY:=ollama}"
: "${LLM_MODEL:=qwen25-14b-ctx8k}"
export LLM_PROVIDER LLM_BASE_URL LLM_API_KEY LLM_MODEL

uv run python experiments/run_phase5c_dryrun.py \
  --goal "ISO27001 の運用文書をチェックして統制不備を是正したい" \
  --knowledge-path examples/iso27001/knowledge \
  --clean-jsonl examples/iso27001/clean_clauses.jsonl \
  --experiment examples_iso27001 \
  --outcomes-dir examples/iso27001/outcomes \
  --evaluator-root src/tsumiki/eval/generated \
  --baseline-paired-diff 0.029 \
  --baseline-label "Phase 6 ISO27001" \
  --seed 42 \
  "$@"
