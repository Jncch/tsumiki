#!/usr/bin/env bash
# Phase 9f: 広報原稿生成 (marketing_post) の開放タスク試走.
# input_modality=free_text (自然言語のみ), output_kind=open.
set -euo pipefail
cd "$(dirname "$0")/../.."

uv run python experiments/run_phase9f_open_ended.py \
  --example examples/marketing_post \
  --experiment phase9f_marketing_post \
  --outcomes-dir examples/marketing_post/outcomes \
  --sample-count 8 \
  --seed 42 \
  "$@"
