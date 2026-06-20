# examples/nda — NDA リファレンス実装

tsumiki の目的駆動 E2E パイプラインで NDA (秘密保持契約) の問題条項を検出 / 是正する例.

## 構造

- `goal.yaml` — 試走で観測された TaskSpec のスナップショット (ドキュメント)
- `knowledge/` — `src/tsumiki/knowledge/skills/nda/ng_patterns/` への symlink (NDA NG パターン 9 件, Agent Skills 形式)
- `clean_clauses.jsonl` — `data/processed/nda_clean_clauses.jsonl` への symlink (中小企業庁ガイドライン由来の clean clauses 10 件)
- `run.sh` — end-to-end 実行スクリプト
- `outcomes/` — 試走結果 (gitignore 対象)

knowledge と clean_clauses は symlink. 実体は tsumiki パッケージ内. ISO27001 (`examples/iso27001/`) も同型構造で同じ `src/tsumiki/runner/e2e.py` を呼び出す.

## 前提

- ホスト (macOS) で ollama 起動 (`ollama serve` または Ollama.app)
- モデル `qwen25-14b-ctx8k` (またはタグ互換のもの) を pull 済
- `data/processed/nda_clean_clauses.jsonl` が生成済 (`experiments/build_clean_clauses.py` 等)
- `uv sync --frozen` で依存インストール済

## 実行

```bash
bash examples/nda/run.sh
```

環境変数で LLM プロバイダを差し替え可:

```bash
LLM_MODEL=hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M bash examples/nda/run.sh
```

クラウド GPT 系を使う場合:

```bash
LLM_BASE_URL=https://api.openai.com/v1 LLM_API_KEY=$OPENAI_API_KEY LLM_MODEL=gpt-4o bash examples/nda/run.sh
```

### β 機能: `--use-compose`

AgentSquare 由来の自動構成探索 (補助情報モード) を併走させる:

```bash
bash examples/nda/run.sh --use-compose
```

現状は **paired_diff には影響しない補助情報モード**. `compose_selected_modules` /
`compose_search_score` が MLflow に追記されるだけで, ベースラインの reuse / zerobase 比較は変更されない.
domain 適応 (archives / prompts) と本物の `benchmark_fn` 実装は Phase 9+ 持ち越し.

詳細は [`docs/experiments/phase7e_summary_2026-06-19.md`](../../docs/experiments/phase7e_summary_2026-06-19.md) §4 を参照.

## 期待結果

Phase 5c / 7b 試走と一致 (seed=42):

| 指標 | 値 |
| --- | --- |
| reuse success_rate | 0.550 |
| zerobase success_rate | 0.289 |
| paired_diff | **+0.261** |
| gate (±0.05) | OK |

## 関連

- Phase 5c 結果: [`docs/experiments/phase5c_e2e_2026-06-19.md`](../../docs/experiments/phase5c_e2e_2026-06-19.md)
- 7b リグレッション: [`docs/experiments/phase7b_packaging_2026-06-19.md`](../../docs/experiments/phase7b_packaging_2026-06-19.md) §4.5
