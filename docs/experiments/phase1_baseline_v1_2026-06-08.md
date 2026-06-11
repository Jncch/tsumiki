# Phase 1 ベースライン v1（クリーンデータ + 3 seed CI、2026-06-08）

v0（[`phase1_baseline_v0_2026-06-08.md`](phase1_baseline_v0_2026-06-08.md)）で判明した 2 つの問題を修正したクリーンな本走。

## 0. v0 から修正した点

| 問題 | 修正 |
| --- | --- |
| 雛形末尾の署名欄・住所欄・オプション条項リストまで CleanClause として混入していた（14 件中 4 件が該当） | `src/tsumiki/data/pipeline.py` に **最小文字数フィルタ (< 50 字除外)** と **`■■オプション条項` マーカー除外** を追加。タブ文字も正規化 |
| `build_labeled_samples` の clause 選択が `(j + rng.randint) % N` で **重複インデックスを返しうる** バグ。同じ (clean, pattern) ペアが複数回 synth に流れ、`clause_id` 衝突 → 評価器エラー | `rng.sample` で **重複なし選択** に変更。`n_synth > clean 数` のときは available 件数で頭打ち |
| LLM 個別呼び出し失敗で run 全体停止 | `synthesize_sample` 呼び出しを try/except で囲み skip + 集計記録 |

## 1. 設定

| 項目 | 値 |
| --- | --- |
| MLflow experiment | `phase1_baseline_v1` |
| モデル | `hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M` |
| seeds | **42, 43, 44**（3 つ） |
| temperature | 0.0 |
| 合成プロンプト | `synthesis.v0.1.0` |
| 検出プロンプト | `baseline.v0.1.0` |
| n_clean | 10（フィルタ後の全 clean を使う） |
| n_synth_per_pattern | 10 |
| 分割比 | train 0.6 / val 0.2 / test 0.2 |
| 評価指標 | NG Recall（主）、Precision、F-beta(β=2)（補助） |
| 1 run 平均時間 | 約 54 分（v0 の 42 分より長い、モデル状態に依存） |

CleanClause は中小企業庁 NDA ひな形 (`guideline02.docx`) から自動抽出した 10 件（フィルタ前 14 件、4 件除外）。

## 2. 集約結果（TEST、3 seed の mean / std / 95% CI）

CI は n=3 の t 分布（df=2、t_0.975=4.303）で算出。サンプル数が小さいため CI は広め。

| 指標 | mean | std | 95% CI |
| --- | --- | --- | --- |
| **macro_recall** | **0.648** | 0.085 | [0.437, 0.859] |
| macro_precision | 0.472 | 0.083 | [0.266, 0.678] |
| **macro_F2** | **0.580** | 0.084 | [0.372, 0.788] |
| weighted_recall | 0.648 | 0.085 | [0.437, 0.859] |
| weighted_precision | 0.472 | 0.083 | [0.266, 0.678] |
| weighted_F2 | 0.580 | 0.084 | [0.372, 0.788] |

VAL（参考、support=18）:

| 指標 | mean | std | 95% CI |
| --- | --- | --- | --- |
| macro_recall | 0.704 | 0.116 | [0.416, 0.991] |
| macro_precision | 0.569 | 0.047 | [0.452, 0.686] |
| macro_F2 | 0.653 | 0.103 | [0.397, 0.908] |

## 3. per-pattern（TEST、各 support=2 × 3 seed = 6 サンプル）

### Recall

| pattern_id | mean | std | 安定性 |
| --- | --- | --- | --- |
| nda_duration_unbounded | **1.000** | 0.000 | 完全安定 |
| nda_remedy_imbalanced | **1.000** | 0.000 | 完全安定 |
| nda_jurisdiction_one_sided | **1.000** | 0.000 | 完全安定 |
| nda_scope_overbroad | 0.833 | 0.289 | ほぼ検出 |
| nda_derivative_undefined | 0.833 | 0.289 | ほぼ検出 |
| nda_disclosure_exception_missing | 0.500 | 0.500 | 不安定 |
| nda_purpose_undefined | 0.333 | 0.289 | 苦手 |
| nda_return_destroy_missing | 0.333 | 0.289 | 苦手 |
| **nda_survival_missing** | **0.000** | 0.000 | **完全見逃し** |

### Precision

| pattern_id | mean | std |
| --- | --- | --- |
| nda_scope_overbroad | 0.889 | 0.192 |
| nda_remedy_imbalanced | 0.889 | 0.192 |
| nda_jurisdiction_one_sided | 0.722 | 0.255 |
| nda_duration_unbounded | 0.467 | 0.058 |
| nda_return_destroy_missing | 0.417 | 0.520 |
| nda_derivative_undefined | 0.411 | 0.084 |
| nda_disclosure_exception_missing | 0.333 | 0.333 |
| nda_purpose_undefined | 0.120 | 0.125 |
| **nda_survival_missing** | **0.000** | 0.000 |

## 4. v0 (汚染) との比較

| 指標 | v0 (seed 42 のみ、データ汚染) | v1 (3 seed mean、クリーン) | 差 |
| --- | --- | --- | --- |
| TEST macro_recall | 0.778 | **0.648** | **-0.130** |
| TEST macro_precision | 0.546 | 0.472 | -0.074 |
| TEST macro_F2 | 0.710 | 0.580 | -0.130 |

汚染データ（署名欄や「（住所）」）に対する LLM 合成は意味的に破綻していたが、見かけ上は recall を持ち上げていた。**クリーンデータでの 0.648 が正味のベースライン**。

## 5. 観察

| 観察 | 仮説／含意 |
| --- | --- |
| seed 間 std = 0.085 | 1 seed だけでベースラインを語るのは危険。CI 必須 |
| 95% CI が広い ([0.437, 0.859]) | n=3 + 各パターン support=2 が原因。n_synth を上げると狭まる |
| 3 パターンが完全安定 (1.000) | duration, remedy, jurisdiction の NG は「明示的な誤った記載」なので検出容易 |
| 1 パターンが完全失敗 (0.000) | `nda_survival_missing` は **書かれていないことを読む** タスク。プロンプトに明示的指示が無い |
| 苦手パターン（purpose, return_destroy, disclosure_exception） | いずれも「欠落」「不明確」系。条文を読んで *無い* ものを推論する難しさ |
| precision 0.472 | 過剰検出傾向は変わらず。1/3 の FP が出ている |

## 6. プロンプト改善の方針（次の打ち手）

`baseline.v0.1.0` プロンプトは「該当する NG パターン id を列挙」とだけ指示している。**欠落検出を明示的に指示** することで `survival_missing` 等の改善が見込める。

検討する改修案:

| ID | 改修 | 期待効果 |
| --- | --- | --- |
| P1 | 「条文に *書かれていない* ことに着目する系のパターン（survival_missing, return_destroy_missing, disclosure_exception_missing）について、明示的な検出ヒントを追加」 | 欠落系 recall の底上げ |
| P2 | 「定義に合致する明示的根拠が条文内に *無い* 場合、列挙しない」を強調（false positive 抑制） | precision 向上 |
| P3 | 各パターンの description を「検出すべきシグナル」と「検出を避ける紛らわしいケース」の 2 段構成に書き直す | recall/precision 同時改善の可能性 |

## 7. 結果ファイル

- MLflow experiment: `phase1_baseline_v1`
- 完了 run（FINISHED）: seed=42, 43, 44 の 3 件
- 集計コマンド:
  ```bash
  uv run python experiments/aggregate_phase1_seeds.py --experiment phase1_baseline_v1 --n-clean 10
  ```

## 8. 再現

```bash
# 1) 雛形を data/raw/nda/chusho_chizai_guideline/guideline02.docx に配置済前提
# 2) CleanClause を再生成（フィルタ反映）
uv run python experiments/build_clean_clauses.py
# → data/processed/nda_clean_clauses.jsonl (10 件)

# 3) 3 seed 連続実行
for s in 42 43 44; do
  uv run python experiments/run_phase1_dryrun.py \
    --model "hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M" \
    --n-synth-per-pattern 10 \
    --n-clean 10 \
    --experiment phase1_baseline_v1 \
    --seed $s
done

# 4) 集計
uv run python experiments/aggregate_phase1_seeds.py --experiment phase1_baseline_v1 --n-clean 10
```

## 9. 関連

- v0（汚染データ）: [`phase1_baseline_v0_2026-06-08.md`](phase1_baseline_v0_2026-06-08.md)
- 試走（qwen 7B）: [`phase1_dryrun_2026-06-08.md`](phase1_dryrun_2026-06-08.md)
- 検証計画書: [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md)
- NG パターン辞書: [`../../src/tsumiki/knowledge/nda/ng_patterns.yaml`](../../src/tsumiki/knowledge/nda/ng_patterns.yaml)
- 試走スクリプト: [`../../experiments/run_phase1_dryrun.py`](../../experiments/run_phase1_dryrun.py)
- 集計スクリプト: [`../../experiments/aggregate_phase1_seeds.py`](../../experiments/aggregate_phase1_seeds.py)
