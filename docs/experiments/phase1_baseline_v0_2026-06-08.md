# Phase 1 ベースライン v0（qwen 14B 本走、2026-06-08）

> **⚠ 注意（2026-06-08 追記）**: 本実験で使った CleanClause セットには、雛形末尾の **署名欄・住所欄・オプション条項リスト** が条項として混入していた（14 件中 4 件が該当）。LLM がこれらに NG 注入を試みた結果、サンプルが意味的に汚染されている。続報の seed=43 で llama-server が 500 エラー（NG 注入出力のパース失敗）を返したことから発覚。
>
> ここに示す数字は**準拠データに汚染がある状態の参考値**として残す。**正式なベースライン数字は [`phase1_baseline_v1_2026-06-08.md`](phase1_baseline_v1_2026-06-08.md) を参照**（クリーンデータでの 3 seed CI 付き）。
>
> 修正: `src/tsumiki/data/pipeline.py` に最小文字数フィルタ (50 字未満を除外) とオプション条項マーカー (`■■オプション条項`) 除外、タブ文字の正規化を追加。`build_labeled_samples` も個別 LLM 失敗を skip して run 全体を停めない設計に変更。

軽量試走（[`phase1_dryrun_2026-06-08.md`](phase1_dryrun_2026-06-08.md)）に続く、主力モデル qwen2.5 14B Instruct でのベースライン本走。Phase 2（再利用の対照実験）の比較対象として **数字を確定する** ことが目的。

## 1. 設定

| 項目 | 値 |
| --- | --- |
| モデル | `hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M` |
| seed | 42 |
| temperature | 0.0 |
| 合成器プロンプト | `synthesis.v0.1.0` |
| 検出器プロンプト | `baseline.v0.1.0` |
| n_clean | 14（CleanClause 全件） |
| n_synth_per_pattern | 10 |
| 分割比 | train 0.6 / val 0.2 / test 0.2（seed 42） |
| 評価指標 | NG Recall（主）、Precision、F-beta(β=2)（補助） |
| 試走時間 | 2554.7 秒（約 42.5 分） |

## 2. データ規模

| 項目 | 値 |
| --- | --- |
| 元雛形 | 中小企業庁 NDA ひな形 1 本 |
| 抽出 CleanClause | 14 件 |
| 合成 NG サンプル | 90 件（9 パターン × 10） |
| Clean サンプル | 14 件（n_clean） |
| 合計 | 104 件 |
| train / val / test | 62 / 20 / 22 |

## 3. 結果（集約指標）

| split | total_support | macro_recall | macro_precision | macro_F2 |
| --- | --- | --- | --- | --- |
| VAL | 18 | 0.833 | 0.572 | 0.743 |
| TEST | **18** | **0.778** | **0.546** | **0.710** |

VAL と TEST で recall に大きな差はなく、splits は安定。

## 4. per-pattern（TEST、各 support=2）

| pattern_id | recall | tp | fp | fn |
| --- | --- | --- | --- | --- |
| nda_scope_overbroad | 1.00 | 2 | 1 | 0 |
| nda_duration_unbounded | 1.00 | 2 | 0 | 0 |
| nda_purpose_undefined | 0.50 | 1 | 2 | 1 |
| nda_disclosure_exception_missing | 0.50 | 1 | 2 | 1 |
| nda_remedy_imbalanced | 1.00 | 2 | 1 | 0 |
| nda_jurisdiction_one_sided | 1.00 | 2 | 1 | 0 |
| nda_return_destroy_missing | 1.00 | 2 | 2 | 0 |
| nda_derivative_undefined | 0.50 | 1 | 1 | 1 |
| nda_survival_missing | 0.50 | 1 | 3 | 1 |

## 5. 試走（qwen 7B）との対比

| 項目 | dryrun (7B) | **baseline_v0 (14B)** | 差分 |
| --- | --- | --- | --- |
| サンプル数 | 28 | 104 | 3.7× |
| TEST support | 9 | 18 | 2× |
| macro_recall | 0.667 | **0.778** | +0.111 |
| macro_precision | 0.537 | 0.546 | +0.009 |
| macro_F2 | 0.616 | **0.710** | +0.094 |
| VAL macro_recall | 0.000（support=0） | 0.833 | 有意化 |

「欠落の検出」3 パターン（disclosure_exception_missing / return_destroy_missing / survival_missing）はすべて改善。14B のコンテクスト保持能力が、明示されていない事項の欠落検出に効いた。

逆に nda_purpose_undefined と nda_derivative_undefined は 7B で 1.00 → 14B で 0.50 と表面的には後退。support=2 のノイズ範囲なので、複数 seed で確認するまでは確定的な解釈を避ける。

## 6. 観察と仮説

| 観察 | 仮説／含意 |
| --- | --- |
| macro_recall +0.111 | モデル能力差が recall に効いた |
| macro_precision はほぼ変わらず (~0.55) | **Precision はモデルではなくプロンプトが律速**。検出基準が「あれば挙げる」型になっており、FP を抑える設計が無い |
| 「欠落」系の改善 | 14B はコンテクスト全体を踏まえて「あるはずのものが無い」を判断できる |
| 一部 recall 後退 | support=2 ゆえノイズ範囲。3 seed × 同条件で CI を確認すべき |
| 試走時間 4 分 → 42 分 | サンプル数 3.7×、モデル 7B→14B でのレイテンシ 2-3× が合わさって所要時間が線形以上に増えた |

## 7. 次の打ち手

| 優先 | 打ち手 | 期待 |
| --- | --- | --- |
| 高 | **複数 seed (3〜5) で CI を出す** | 上記の「後退」が真の差かノイズか確定 |
| 高 | **プロンプト改善（precision 向上）** | "明示的な根拠が条文内にある場合のみ列挙" 等の制約。F2 で +0.05 を狙う |
| 中 | n_synth を 20 に増やし support>=4/pattern を確保 | 結果の統計性向上、本走 1.5×（約 75 分） |
| 中 | Phase 2 対照実験設計 | T2（NG 条項修正）への知識層再利用、再利用率測定 |
| 低 | クラウドの強モデル（GPT-4 系等）で上限確認 | CLAUDE.md §3 の「最終結論はクラウド」原則 |

## 8. 記録

- MLflow experiment: `phase1_baseline_v0`
- run name: `dryrun_20260608_165040`（スクリプト名が dryrun のまま流用、内容は本走）
- 記録 params: model, quantization_tag, prompt_version, seed, temperature, contract_type, phase, ollama_version, synth_model, synth_prompt_version, n_train, n_val, n_test, n_synth_per_pattern, n_clean, ng_book_version
- 記録 metrics: `val.*`, `test.*` の macro_recall/precision/fbeta、weighted_*、per-pattern recall/precision/fbeta/support、total_support、beta

閲覧:
```bash
mlflow ui --backend-store-uri file:./mlruns
```

## 9. 再現

```bash
uv run python experiments/run_phase1_dryrun.py \
  --model "hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M" \
  --n-synth-per-pattern 10 \
  --n-clean 14 \
  --experiment phase1_baseline_v0 \
  --seed 42
```

## 10. 関連

- 試走レポート: [`phase1_dryrun_2026-06-08.md`](phase1_dryrun_2026-06-08.md)
- 検証計画書: [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md)
- NG パターン辞書: [`../../src/tsumiki/knowledge/nda/ng_patterns.yaml`](../../src/tsumiki/knowledge/nda/ng_patterns.yaml)
- 試走スクリプト: [`../../experiments/run_phase1_dryrun.py`](../../experiments/run_phase1_dryrun.py)
