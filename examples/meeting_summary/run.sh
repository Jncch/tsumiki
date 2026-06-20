#!/usr/bin/env bash
# Phase 9f: 議事録要約 (meeting_summary) の semi-open 試走.
# input_modality=mixed (doc + free_text), output_kind=semi_open.
set -euo pipefail
cd "$(dirname "$0")/../.."

uv run python experiments/run_phase9f_open_ended.py \
  --example examples/meeting_summary \
  --experiment phase9f_meeting_summary \
  --outcomes-dir examples/meeting_summary/outcomes \
  --sample-count 8 \
  --seed 42 \
  "$@"
