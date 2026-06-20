# examples/iso27001 — ISO27001 監査チェックのリファレンス実装

tsumiki の目的駆動 E2E パイプラインで ISO27001 統制不備を検出 / 是正する例.

NDA (`examples/nda/`) と **同じ `src/tsumiki/runner/e2e.py`** を呼び出す. ドメイン非依存性の実地確証 (計画書 §10.3).

## 構造

- `goal.yaml` — 試走で観測された TaskSpec のスナップショット (ドキュメント)
- `knowledge/` — `src/tsumiki/knowledge/skills/iso27001/audit_findings/` への symlink (統制不備 9 パターン, Agent Skills)
- `clean_clauses.jsonl` — `data/processed/iso27001_clean_clauses.jsonl` への symlink (公開規程テンプレート由来 10 件)
- `run.sh` — end-to-end 実行スクリプト
- `outcomes/` — 試走結果 (gitignore 対象)

## 前提

- ホスト (macOS) で ollama 起動
- モデル `qwen25-14b-ctx8k` を pull 済
- `data/processed/iso27001_clean_clauses.jsonl` が生成済 (`experiments/build_iso27001_clean_clauses.py`)
- `uv sync --frozen` で依存インストール済

## 実行

```bash
bash examples/iso27001/run.sh
```

### β 機能: `--use-compose`

AgentSquare 由来の自動構成探索 (補助情報モード) を併走させる:

```bash
bash examples/iso27001/run.sh --use-compose
```

NDA と同様, 現状は **paired_diff には影響しない補助情報モード**.
`compose_selected_modules` / `compose_search_score` が MLflow に追記される.
詳細は [`docs/experiments/phase7e_summary_2026-06-19.md`](../../docs/experiments/phase7e_summary_2026-06-19.md) §4 を参照.

## 期待結果

Phase 6 / 7b 試走と一致 (seed=42):

| 指標 | 値 |
| --- | --- |
| reuse success_rate | 0.410 |
| zerobase success_rate | 0.381 |
| paired_diff | **+0.029** |
| gate (±0.05) | OK |

NDA と比べ paired_diff が小さい. 「ISO27001 では zerobase 自身が高い (0.381 vs NDA 0.289) ため相対効果が縮む」現象が観測されている (Phase 6 §5).

## 関連

- Phase 6 結果: [`docs/experiments/phase6_e2e_2026-06-19.md`](../../docs/experiments/phase6_e2e_2026-06-19.md)
- 7b リグレッション: [`docs/experiments/phase7b_packaging_2026-06-19.md`](../../docs/experiments/phase7b_packaging_2026-06-19.md) §4.5
