# tsumiki

タスク実行エージェント自動生成における「知識層再利用」仮説の最小検証フレーム.

再利用可能な部品 (知識層 / ツール層) を合成してタスクごとのエージェントを構築するアプローチを検証する.
名前は積み木に由来する.

詳細な方針・計画は [`docs/agent_reuse_verification_plan.md`](docs/agent_reuse_verification_plan.md) を,
リポジトリ作業ルールは [`CLAUDE.md`](CLAUDE.md) を参照.

## 現状 (2026-06-20)

- Phase 1〜7e 完了. test 290/290 PASS.
- N=2 ドメイン (NDA / ISO27001) で「自然言語の目的 → 評価器流用 → end-to-end paired_diff 改善」が再現:
  - NDA: paired_diff **+0.261** (reuse 0.550 vs zerobase 0.289, seed=42)
  - ISO27001: paired_diff **+0.029** (reuse 0.410 vs zerobase 0.381, seed=42)
- AgentSquare partial vendoring (modules / search / evolution / recombination / predictor) を `src/tsumiki/policy/agentsquare/` に取り込み.
  LLM 差し替えと benchmark_fn DI 化済 (詳細は [`docs/agentsquare_vendoring.md`](docs/agentsquare_vendoring.md)).

## 対応 LLM プロバイダ

`src/tsumiki/llm/client.py` は OpenAI / AzureOpenAI SDK を経由し, 設定層で
プロバイダを切り替える (CLAUDE.md §3 プロバイダ非依存ルール). 詳細は
[`.env.example`](.env.example) を参照.

| プロバイダ | `LLM_PROVIDER` | `LLM_BASE_URL` | 備考 |
| --- | --- | --- | --- |
| ローカル ollama | `openai_compatible` (default) | `http://localhost:11434/v1` | Qwen2.5-14B 等. 開発・探索ループの主用途 |
| OpenAI 本家 | `openai_compatible` | `https://api.openai.com/v1` | gpt-5 等 |
| Azure OpenAI | `azure_openai` | (`AZURE_OPENAI_ENDPOINT`) | gpt-5.4 等. deployment 名で指定 |
| Anthropic Claude | `openai_compatible` | `https://api.anthropic.com/v1/` | OpenAI 互換エンドポイント経由. claude-opus-4-7 等 |
| Google Gemini | `openai_compatible` | `https://generativelanguage.googleapis.com/v1beta/openai/` | OpenAI 互換エンドポイント経由. gemini-2.5-pro 等 |
| OpenRouter | `openai_compatible` | `https://openrouter.ai/api/v1` | 複数プロバイダの横断 |

実走実績は **ollama Qwen2.5-14B** と **Azure gpt-5.4** で確認済 (Phase 8-6).
他は構造確認 smoke のみで, ライブ実走は Phase 9+ で順次追加予定.

関連 Zenn 記事:

- Part 1〜2 (Phase 0〜4 + 5a〜5b): [https://zenn.dev/jnch/articles/68b0ede8c04aa8](https://zenn.dev/jnch/articles/68b0ede8c04aa8)
- Part 3 (Phase 5c / 6 / 7): 別途公開予定

## ディレクトリ

| パス | 内容 |
| --- | --- |
| `src/tsumiki/` | パッケージ本体 (`knowledge/` 知識資産, `goal/` 目的・評価仕様, `eval/` 評価器, `runner/` E2E, `policy/` ポリシー層 + AgentSquare vendoring, `llm/` プロバイダ非依存設定層, `data/` データ層, `smoke/` サニティ) |
| `examples/nda/`, `examples/iso27001/` | 同一 runner を呼ぶリファレンス実装. それぞれ `run.sh` で E2E を実行可能 |
| `experiments/` | 実験スクリプト (再現可能な ad-hoc CLI) |
| `tests/` | pytest (290 件) |
| `docs/` | 方針・計画書, 各 Phase の結果報告書 |
| `data/`, `var/ollama/models/` | データ・モデル保存先 (コミットしない) |

## クイックスタート

前提:

- macOS, uv, ollama (ホスト・ネイティブ macOS, Metal 加速).
- 詳細は [`CLAUDE.md`](CLAUDE.md) §3 (LLM プロバイダ) と §12 (実行コマンド) を参照.

```bash
# 1. 依存同期
uv sync --frozen

# 2. ollama モデル保存先をプロジェクト内に固定して起動
scripts/start_ollama.sh

# 3. 検証用モデルを取得
scripts/pull_models.sh

# 4. 日本語サニティチェック
uv run python -m tsumiki.smoke.japanese_check

# 5. NDA リファレンス実装を実行
bash examples/nda/run.sh

# 6. ISO27001 リファレンス実装を実行
bash examples/iso27001/run.sh
```

`.env` は `.env.example` をコピーして編集する. `.env` は `.gitignore` 対象.

## β 機能: `--use-compose`

`examples/*/run.sh --use-compose` で AgentSquare 由来の自動構成探索 (補助情報モード) を併走できる.
現状は **paired_diff には影響しない補助情報モード** で, `compose_selected_modules` / `compose_search_score` を
MLflow に追記するのみ. domain 適応 (archives / prompts) と本物の `benchmark_fn` 実装は Phase 9+ 持ち越し.

詳細は [`docs/experiments/phase7e_summary_2026-06-19.md`](docs/experiments/phase7e_summary_2026-06-19.md) §4 を参照.

## NDA 雛形データの取得

NDA 雛形ファイルは Akamai CDN の WAF によって自動ダウンロードがブロックされるため, ブラウザで手動取得する.

```bash
# 未配置ファイルと出典 URL を一覧する
uv run python -c "from pathlib import Path; from tsumiki.data.sources.loader import load_nda_templates_catalog as L; cat=L(); [print(f'{f.target_path}\n  {f.url}') for s in cat.sources for f in s.files if not f.exists(Path.cwd())]"
```

各 URL をブラウザで開き, 表示された `target_path` にそのままのファイル名で保存する.
出典・ライセンス (政府標準利用規約 v2.0 相当) の詳細は
[`src/tsumiki/data/sources/nda_templates.yaml`](src/tsumiki/data/sources/nda_templates.yaml) を参照.

## 開発

```bash
uv run pytest                       # テスト 290 件
uv run ruff check && uv run ruff format
uv run pyright                      # 暫定
```

コントリビューション方針は [`CONTRIBUTING.md`](CONTRIBUTING.md) を参照.

## ライセンス

- 本リポジトリ: Apache License 2.0 ([`LICENSE`](LICENSE))
- AgentSquare 由来部分 (`src/tsumiki/policy/agentsquare/`): Apache-2.0 (上流継承).
  詳細は [`NOTICE`](NOTICE) と [`THIRD_PARTY_LICENSES/`](THIRD_PARTY_LICENSES/) を参照.
