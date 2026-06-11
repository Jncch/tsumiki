#!/usr/bin/env bash
# ollama をプロジェクト内モデルパスで起動する。
# CLAUDE.md §3: OLLAMA_MODELS は ollama 起動「前」にエクスポートする必要がある。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export OLLAMA_MODELS="${PROJECT_ROOT}/var/ollama/models"

mkdir -p "${OLLAMA_MODELS}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "[start_ollama] ollama がインストールされていません" >&2
  echo "  - macOS app: https://ollama.com/download" >&2
  echo "  - or brew:  brew install ollama" >&2
  exit 1
fi

if pgrep -x ollama >/dev/null 2>&1; then
  echo "[start_ollama] 既に ollama プロセスが起動しています。"
  echo "  OLLAMA_MODELS を反映させるには一度終了してから本スクリプトを再実行してください:"
  echo "  pkill ollama"
  exit 0
fi

echo "[start_ollama] OLLAMA_MODELS=${OLLAMA_MODELS}"
echo "[start_ollama] ollama serve をフォアグラウンドで起動します（Ctrl-C で停止）。"
exec ollama serve
