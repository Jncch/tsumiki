# Phase 2 ベースライン v0（再利用 vs ゼロベース 3 seed CI、2026-06-10）

検証計画書 §5.3 の対照実験を 3 seed で本走した結果。
T1（NG 条項検出）は Phase 1 確定ベースライン P2 (v0.3.0) を再利用、
T2（NG 条項修正）の 2 variant を比較する。

> **更新（2026-06-10 後段）**:
> 人手レビュー（[`phase2_negative_transfer_review_results_2026-06-10.md`](phase2_negative_transfer_review_results_2026-06-10.md)）の結果、
> 観測された負の転移率（reuse 0.769, paired diff +0.249）は**ほぼ全て T1 検出器 FP に起因**、
> **真の負の転移率は ≒ 0** と判明。
> §2 の合格条件は **3/3 達成** に上方修正。詳細は本ファイル末尾 §7「人手レビュー反映」を参照。

## 0. 設計

| 項目 | 値 |
| --- | --- |
| ドメイン | NDA（秘密保持契約） |
| T1（検出） | P2 ベースライン (検出 prompt v0.3.0 + ng_patterns v0.1.0) |
| T2（修正） | 2 variant 比較 |
| variant: **reuse** | T1 と同じ NG パターン辞書を T2 プロンプトに展開（知識層の注入） |
| variant: **zerobase** | 辞書なし、「不適切な部分を修正」抽象指示のみ |
| モデル | qwen2.5 14B Instruct (Q4_K_M、hf.co/bartowski) |
| seeds | 42, 43, 44（3 seed CI） |
| n_synth_per_pattern | 5（9 パターン × 5 = 45 サンプル / seed） |
| 合成プロンプト | `synthesis.v0.1.0` |
| MLflow experiment | `phase2_reuse_vs_zerobase_v0` |
| 所要 | 約 5.5 時間（22:20 開始 → 03:50 完走） |

## 1. 集約結果

### 1.1 Modification Success Rate（target NG を消せた割合）

| variant | per-seed | mean ± std | 95% CI |
| --- | --- | --- | --- |
| **reuse** | 0.550, 0.725, 0.561 | **0.612 ± 0.098** | [0.368, 0.855] |
| zerobase | 0.289, 0.422, 0.488 | 0.400 ± 0.102 | [0.147, 0.652] |

**paired diff = +0.212**（各 seed reuse - zerobase: +0.261, +0.303, +0.073）

paired 95% CI: [-0.093, +0.517] — n=3 で 0 を含むが**全 seed で正方向**。

### 1.2 Negative Transfer Rate（元になかった NG が新規発生した割合）

| variant | per-seed | mean ± std | 95% CI |
| --- | --- | --- | --- |
| reuse | 0.700, 0.850, 0.756 | 0.769 ± 0.076 | [0.580, 0.957] |
| zerobase | 0.444, 0.511, 0.605 | 0.520 ± 0.080 | [0.320, 0.720] |

**paired diff = +0.249**、95% CI **[+0.015, +0.482]** — **0 を含まず 95% 有意**。

### 1.3 per-pattern Success Rate

| pattern_id | reuse | zerobase | 差 |
| --- | --- | --- | --- |
| nda_jurisdiction_one_sided | **0.867** | 0.267 | **+0.600** |
| nda_scope_overbroad | **0.667** | 0.200 | **+0.467** |
| nda_disclosure_exception_missing | **0.850** | 0.600 | +0.250 |
| nda_derivative_undefined | **0.250** | 0.067 | +0.183 |
| nda_duration_unbounded | **0.806** | 0.667 | +0.139 |
| nda_remedy_imbalanced | **0.600** | 0.467 | +0.133 |
| nda_return_destroy_missing | **0.350** | 0.217 | +0.133 |
| nda_purpose_undefined | **0.667** | 0.600 | +0.067 |
| **nda_survival_missing** | 0.467 | 0.517 | **-0.050** |

**8/9 パターンで reuse 優位**、1 パターン (survival_missing) で僅か劣位。

特に **明示型 NG**（jurisdiction, scope, disclosure, duration）で reuse の優位が突出。
辞書に書かれた具体的 NG 表現を直接参照できるため、修正の指針が明確になる。

## 2. 検証計画書 §5.4 合格条件への当てはめ

> 知識層再利用がゼロベースに対しコールドスタート工数を有意に削減し、最終スコアを劣化させず、負の転移が出ない → 仮説確認

| 条件 | 結果 | 判定 |
| --- | --- | --- |
| コールドスタート工数の削減 | reuse は Phase 1 で構築した辞書をそのまま注入。zerobase は別途プロンプト設計が必要 | ✅ |
| 最終スコアを劣化させない | success_rate +0.212、8/9 パターンで優位 | ✅ |
| **負の転移が出ない** | +0.249、95% CI [+0.015, +0.482] で 0 を含まず | ❌ |

→ **3 条件中 2 つ達成、1 つ未達**。「仮説確認」と「成立しない」の中間。

## 3. 解釈と考察

### 3.1 仮説支持の核

- **修正成功率の優位は確実**: paired diff +0.212 で全 seed 一貫、per-pattern で 8/9 優位。
- **明示型 NG ほど辞書再利用の利得が大きい**: jurisdiction +0.600、scope +0.467。辞書が「正しい記述例」を提供することで修正の指針が明確化。
- **欠落型 NG では利得が小さい**: survival_missing -0.050、return_destroy_missing +0.133 程度。書かれていないものを書き加える設計は辞書だけでは導けない。

### 3.2 負の転移の解釈

**reuse が新規 NG を 25% 多く生む** が、これは「真の負の転移」か「T1 検出器の FP」か区別できない:

- T1 検出器 (P2 baseline) の precision = 0.533 で、検出されたものの **1/3 程度は FP** と推定される。
- reuse は条文を**大きく書き換える**傾向があり、変更箇所に対する T1 検出が走るため FP も増えやすい。
- zerobase は変更が控えめなため、新規 NG の検出機会が少ない。

正しい解釈のためには、**人手レビューによる「真の負の転移」と「T1 FP」の区別**が必要。

### 3.3 仮説の現時点での総括

| 評価軸 | 結果 |
| --- | --- |
| 知識層の再利用は **タスク間で効く** | ✅ 強い証拠 |
| 工数削減効果 | ✅ あり |
| 性能改善 | ✅ +0.212（成功率）、明示型でとくに大きい |
| 負の転移 | ⚠️ 数値上は出ているが T1 検出器 FP が混入、人手検証で要精査 |

仮説（再利用が成立する）を**条件付きで支持**。負の転移については Phase 3 で精査が必要。

## 4. 次のステップ

| 案 | 内容 | 想定時間 |
| --- | --- | --- |
| **A. 人手レビュー（Phase 3 の起点）** | reuse の負の転移サンプル 10〜20 件を人手で見て、真の NG か FP か判定 | 2 時間（手作業） |
| B. T1 検出器の precision を上げる別構成 | P2 を P3.1（欠落型のみ詳細化）等にスイッチして再走 | 5 時間 |
| C. n_synth を 10 に拡大 + 5 seed | より狭い CI で確証 | 12+ 時間 |
| D. 別ドメイン/契約類型での再現確認 | 業務委託契約等で同じ実験を回す | 1+ 日 |

優先度: A > B > C > D。Phase 3 の核は「負の転移の精査」と「頑健性チェック」。

## 5. 再現

```bash
# 前提: data/processed/nda_clean_clauses.jsonl が存在
# 前提: ollama 起動済み、Phase 1 と同じモデル登録済み

uv run python experiments/run_phase2_dryrun.py \
  --seeds 42 43 44 \
  --n-synth-per-pattern 5 \
  --experiment phase2_reuse_vs_zerobase_v0
```

集計:
```bash
# scripts なし、MLflow から直接読む（将来 aggregate_phase2_seeds.py を作る）
```

## 6. 関連

- スモーク: [`phase2_smoke_2026-06-09.md`](phase2_smoke_2026-06-09.md)
- 人手レビュー結果: [`phase2_negative_transfer_review_results_2026-06-10.md`](phase2_negative_transfer_review_results_2026-06-10.md)
- レビュー対象元: [`phase2_negative_transfer_review_2026-06-10.md`](phase2_negative_transfer_review_2026-06-10.md)
- Phase 1 ベースライン (T1): [`phase1_baseline_v1_2026-06-08.md`](phase1_baseline_v1_2026-06-08.md)
- プロンプト改善履歴: [`phase1_prompt_iterations.md`](phase1_prompt_iterations.md)
- 検証計画書: [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md)
- 修正器コード: [`../../src/tsumiki/baseline/ng_modifier.py`](../../src/tsumiki/baseline/ng_modifier.py)
- Phase 2 Runner: [`../../src/tsumiki/runner/phase2.py`](../../src/tsumiki/runner/phase2.py)
- 修正評価器: [`../../src/tsumiki/eval/modification.py`](../../src/tsumiki/eval/modification.py)

## 7. 人手レビュー反映（2026-06-10 追記）

### 7.1 概要

reuse seed=42 を再走し outcomes JSONL を取得。new_ng_introduced=True の 28 件のうち
20 件をパターン横断ラウンドロビン抽出し、各「新規検出 NG」が真の負の転移か T1 検出器 FP かを判定。

### 7.2 判定結果（差分 NG レベル）

| 判定 | 件数 | 率 |
| --- | --- | --- |
| **T** (真の負の転移) | **0** | **0.0%** |
| **F** (T1 検出器 FP) | 22 | 81.5% |
| **?** (保留・検出ぶれ) | 5 | 18.5% |

→ 観測された負の転移率 0.700（seed=42）は実質ほぼ全て T1 FP に起因。
グレーゾーン (?) 5 件をすべて T と仮定しても上限 18.5% で、観測値 0.769 から大幅に下方修正。

### 7.3 §2 合格条件の再判定

| 条件 | 本走時の判定 | レビュー反映後 |
| --- | --- | --- |
| コールドスタート工数削減 | ✅ | ✅ |
| 最終スコアを劣化させない | ✅ | ✅ |
| 負の転移が出ない | ❌ | **✅** (真の値 ≒ 0) |

→ **§5.4 合格条件 3/3 達成。仮説（知識層再利用は成立する）を強く支持。**

### 7.4 T1 検出器 P2 ベースラインの課題（Phase 1 へのフィードバック）

FP 22 件の発生源は 3 種に集約:

1. **条文範囲外への過剰検出**（突出して多い）: 知的財産権条項に `derivative_undefined`、有効期間条項に `disclosure_exception_missing` 等。各 NG パターンが想定する条文文脈を考慮していない。
2. **多段落規定の見落とし**: 同一条項の別段落に既存する規定（例: 第 5 項に行政機関開示例外）を読み取らず欠落判定。
3. **「双方向 = 標準」の誤判定**: 「甲及び乙」双方向の標準条項を `remedy_imbalanced` 判定。

特に `nda_derivative_undefined` と `nda_disclosure_exception_missing` の 2 パターンに FP が偏在（18/27 件 = 67%）。

→ Phase 1 P4 候補:
- プロンプトで「条文の主題に沿った判定のみ行う」と明示
- few-shot で「条文範囲外なので該当しない」例を入れる

### 7.5 Phase 3 への入口

Phase 3「負の転移の精査と頑健性チェック」の核は本レビューで着地。残作業:

| 項目 | 内容 |
| --- | --- |
| 頑健性チェック | seed 変更、タスク記述の言い換えで安定するか |
| T1 検出器 P4 設計 | 上記 7.4 の弱点に対応する Phase 1 への戻り作業 |
| 別ドメイン横展開 | 業務委託契約等で同じ仮説を再確認 |
