#!/usr/bin/env bash
# Phase 9f: 販促キャンペーン案 (campaign_proposal) の試走.
# input_modality=none (入力なし), output_kind=open.
set -euo pipefail
cd "$(dirname "$0")/../.."

uv run python experiments/run_phase9f_open_ended.py \
  --example examples/campaign_proposal \
  --experiment phase9f_campaign_proposal \
  --outcomes-dir examples/campaign_proposal/outcomes \
  --sample-count 8 \
  --seed 42 \
  "$@"
