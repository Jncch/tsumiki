#!/usr/bin/env bash
# Phase 9f: 仕様書 → テストケース (spec_to_tests) の試走.
# input_modality=doc, output_kind=semi_open.
set -euo pipefail
cd "$(dirname "$0")/../.."

uv run python experiments/run_phase9f_open_ended.py \
  --example examples/spec_to_tests \
  --experiment phase9f_spec_to_tests \
  --outcomes-dir examples/spec_to_tests/outcomes \
  --sample-count 8 \
  --seed 42 \
  "$@"
