#!/usr/bin/env bash
# 初期モデルセット（Qwen2.5 14B/7B、ELYZA-JP 8B）を pull する。
# 事前に scripts/start_ollama.sh を別シェルで起動しておくこと。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export OLLAMA_MODELS="${PROJECT_ROOT}/var/ollama/models"

MODELS=(
  "hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M"
  "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"
  "hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF:latest"
)

for m in "${MODELS[@]}"; do
  echo "[pull_models] pulling ${m}"
  ollama pull "${m}"
done

echo "[pull_models] done. installed models:"
ollama list
