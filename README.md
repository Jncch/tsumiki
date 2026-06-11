# tsumiki

タスク実行エージェント自動生成における「知識層再利用」仮説の最小検証。

詳細な方針・計画は [`docs/agent_reuse_verification_plan.md`](docs/agent_reuse_verification_plan.md) を、
リポジトリでの作業ルールは [`CLAUDE.md`](CLAUDE.md) を参照すること。

## クイックスタート

前提:
- macOS、colima、Docker CLI、uv、ollama（ホスト・ネイティブ macOS）。

```bash
# 1. 依存同期（ローカル開発用）
uv sync --frozen

# 2. ollama モデル保存先をプロジェクト内に固定して起動
scripts/start_ollama.sh

# 3. 検証用モデルを取得
scripts/pull_models.sh

# 4. 日本語サニティチェック
uv run python -m tsumiki.smoke.japanese_check

# 5. コンテナで動かす場合
colima start
docker compose up -d
```

`.env` は `.env.example` をコピーして編集する。`.env` 自身は `.gitignore` 対象。

## ディレクトリ

| パス | 内容 |
| --- | --- |
| `src/tsumiki/` | パッケージ本体 |
| `experiments/` | 実験スクリプト・設定 |
| `tests/` | pytest |
| `docs/` | 方針・計画 |
| `data/` | 業務データ（コミットしない） |
| `var/ollama/models/` | ollama モデル保存先（コミットしない） |

## NDA 雛形データの取得

NDA 雛形ファイルは Akamai CDN の WAF によって自動ダウンロードがブロックされるため、ブラウザで手動取得する。

```bash
# 未配置ファイルと出典 URL を一覧する
uv run python -c "from pathlib import Path; from tsumiki.data.sources.loader import load_nda_templates_catalog as L; cat=L(); [print(f'{f.target_path}\n  {f.url}') for s in cat.sources for f in s.files if not f.exists(Path.cwd())]"
```

各 URL をブラウザで開き、表示された `target_path` にそのままのファイル名で保存する。
出典・ライセンス（政府標準利用規約 v2.0 相当）の詳細は
[`src/tsumiki/data/sources/nda_templates.yaml`](src/tsumiki/data/sources/nda_templates.yaml) を参照。
