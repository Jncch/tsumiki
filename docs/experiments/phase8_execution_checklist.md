# Phase 8 実走チェックリスト

Phase 8-6 (ユーザー実走) と 8-7 / 8-8 / 8-9 の手順をまとめたもの.
更新時刻ベースで上から順に消化する.

---

## 8-6: ユーザー実走 — `--use-compose` 経由 paired_diff 再現確認

### 前提

- ollama (ホスト・ネイティブ macOS) が起動
- `var/ollama/models/` にモデル `qwen25-14b-ctx8k` (またはタグ互換) が pull 済
- もしくは Azure OpenAI 経由で実走する場合は `.env` に `AZURE_OPENAI_*` を設定

### ollama 経由 (推奨, ローカル)

```bash
# ollama 起動 (別端末)
scripts/start_ollama.sh

# NDA
bash examples/nda/run.sh --use-compose

# ISO27001
bash examples/iso27001/run.sh --use-compose
```

### Azure OpenAI 経由 (オプション)

```bash
# .env に AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_VERSION を設定
# モデルは GPT-5.4 等を想定
source .env
bash examples/nda/run.sh --use-compose \
  --llm-provider azure_openai \
  --llm-model gpt-5.4 \
  --azure-api-version "$AZURE_OPENAI_API_VERSION"
```

### 確認指標 (gate ±0.05)

| ドメイン | 期待値 (Phase 5c/6) | 再現許容範囲 |
| --- | --- | --- |
| NDA paired_diff | **+0.261** | +0.211〜+0.311 |
| ISO27001 paired_diff | **+0.029** | -0.021〜+0.079 |

### 取得する MLflow 指標

- `paired_diff` (reuse - zerobase)
- `reuse_success_rate`
- `zerobase_success_rate`
- `compose_selected_modules` (補助情報, 文字列リスト)
- `compose_search_score` (補助情報, float)
- run id (記事 §7 への引用用)

### 結果記録

実走後, 以下を `phase8_execution_<date>.md` (スケルトン参照) に記録:

1. 実行日時, モデル名, 量子化タグ, ollama / Azure バージョン
2. NDA / ISO27001 の paired_diff 実測値
3. `compose_selected_modules` / `compose_search_score`
4. gate 判定 (OK / NG)
5. MLflow run id と experiment 名

---

## 8-7: 実走結果を記事 §7 / §9 に反映

`docs/experiments/phase8_zenn_draft_v0.md` の以下セクションを更新:

- §7 主要結果サマリ表: 実走 paired_diff 数値を反映 (現状はドラフト時点の Phase 5c/6 値そのまま)
- §9 制約と次の問い: ollama / Azure どちらで再現したかを明記
- (任意) §3 / §4 末尾に `compose_selected_modules` のスナップショット追記

更新後 `phase8_zenn_draft_v1.md` にリネーム or 同ファイル更新.

---

## 8-8: 記事最終版 + リポジトリ public 化 (ユーザー作業)

1. Zenn 投稿準備
   - `phase8_zenn_draft_v1.md` を Zenn CLI or 手動 paste で投稿
   - 前回記事 (Part 1〜2) との相互リンクを確認
2. GitHub リポジトリ public 化
   - `data/` および `var/` が `.gitignore` に入っていることを最終確認
   - `.env` がコミットされていないことを最終確認
   - secrets scan (`gh secret list`, `git log -- .env` などで漏洩がないか確認)
3. 記事公開後にリポジトリ public 化, README に Zenn Part 3 リンクを追記する PR を当てる

---

## 8-9: Phase 8 結果報告書

`docs/experiments/phase8_execution_<date>.md` を完成させる.
スケルトンは [phase8_execution_skeleton.md](./phase8_execution_skeleton.md) を参照.
