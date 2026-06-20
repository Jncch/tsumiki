# Phase 8 結果報告書 (スケルトン)

> 実走後 `phase8_execution_<date>.md` にコピーして埋める. このファイル自体は雛形.

## 0. メタ情報

| 項目 | 値 |
| --- | --- |
| 実行日 | YYYY-MM-DD |
| 実行者 | (ユーザー名) |
| LLM プロバイダ | openai_compatible / azure_openai |
| ベース URL / エンドポイント | (例: http://localhost:11434/v1) |
| モデル / 量子化タグ | (例: qwen25-14b-ctx8k / Q4_K_M) |
| seed | 42 |
| temperature | 0 |
| ollama / Azure バージョン | (例: ollama 0.x.x) |
| MLflow experiment 名 | examples_nda / examples_iso27001 |

## 1. 目的

Phase 7e-6 で導入した `--use-compose` 経由で,
Phase 5c (NDA) / Phase 6 (ISO27001) の paired_diff 数値が
±0.05 範囲で再現することを確認する.

## 2. 実行コマンド

```bash
# ollama 起動
scripts/start_ollama.sh

# NDA
bash examples/nda/run.sh --use-compose

# ISO27001
bash examples/iso27001/run.sh --use-compose
```

(Azure OpenAI で実行した場合は対応コマンドに置換)

## 3. 結果

### 3.1 NDA

| 指標 | Phase 5c 基準値 | 今回実測値 | 差 | gate (±0.05) |
| --- | --- | --- | --- | --- |
| reuse success_rate | 0.550 | TBD | TBD | - |
| zerobase success_rate | 0.289 | TBD | TBD | - |
| **paired_diff** | **+0.261** | TBD | TBD | OK / NG |
| compose_selected_modules | - | TBD | - | - |
| compose_search_score | - | TBD | - | - |
| MLflow run id | - | TBD | - | - |

### 3.2 ISO27001

| 指標 | Phase 6 基準値 | 今回実測値 | 差 | gate (±0.05) |
| --- | --- | --- | --- | --- |
| reuse success_rate | 0.410 | TBD | TBD | - |
| zerobase success_rate | 0.381 | TBD | TBD | - |
| **paired_diff** | **+0.029** | TBD | TBD | OK / NG |
| compose_selected_modules | - | TBD | - | - |
| compose_search_score | - | TBD | - | - |
| MLflow run id | - | TBD | - | - |

## 4. 観察

(TBD: 実走時の所感. 例: ollama 応答時間, MLflow 記録の正常性, compose 選択モジュールの妥当性, etc.)

## 5. gate 判定

| ドメイン | gate | 備考 |
| --- | --- | --- |
| NDA | OK / NG | - |
| ISO27001 | OK / NG | - |

両方 OK の場合のみ Phase 8-7 (記事最終版反映) に進む.
NG の場合は再現性問題として原因調査を優先する.

## 6. compose 補助情報の所感

`--use-compose` は補助情報モードのため paired_diff を直接動かさないが,
`compose_selected_modules` に「現状の archives / prompts (alfworld 由来) が
どう振る舞ったか」が出る. domain 適応の重要性を裏付ける材料として記録:

- 観察された selected_modules: TBD
- search_score: TBD
- 所感: TBD

## 7. 次の問い (Phase 9+ への申し送り)

- benchmark_fn の本物実装 (agentsquare 合成 chat_fn)
- archives / prompts の domain 適応 (NDA / ISO27001 用)
- N=3 ドメイン追加
- 3 seed CI
- 人手較正
- Phase 7-bonus-1 (generator 主 metric 整合)
- Phase 7-bonus-2 (input_signature schemas 固定)

## 8. 関連

- 実走チェックリスト: [phase8_execution_checklist.md](./phase8_execution_checklist.md)
- Zenn ドラフト: [phase8_zenn_draft_v0.md](./phase8_zenn_draft_v0.md)
- Phase 5c 結果: [phase5c_e2e_2026-06-19.md](./phase5c_e2e_2026-06-19.md)
- Phase 6 結果: [phase6_e2e_2026-06-19.md](./phase6_e2e_2026-06-19.md)
- Phase 7e 統合: [phase7e_summary_2026-06-19.md](./phase7e_summary_2026-06-19.md)
