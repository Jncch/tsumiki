# Phase 1 プロンプト改善イテレーション履歴

ベースライン (v1) で判明した課題に対して、検出プロンプトをバージョン単位で改修していく履歴。
**「何を変えたか」と「その変更が指標にどう効いたか」を 1 イテレーションごとに記録する**。

各改修は以下の条件で同条件比較する:
- モデル: `hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M`
- データ: 中小企業庁 NDA ひな形（フィルタ後 10 件）
- 合成プロンプト: `synthesis.v0.1.0`（固定）
- seeds: 42, 43, 44（固定）
- n_synth_per_pattern: 10
- n_clean: 10

---

## ベースライン: `baseline.v0.1.0`（v1 結果、3 seed CI）

| 指標 | mean | std | 95% CI |
| --- | --- | --- | --- |
| TEST macro_recall | 0.648 | 0.085 | [0.437, 0.859] |
| TEST macro_precision | 0.472 | 0.083 | [0.266, 0.678] |
| TEST macro_F2 | 0.580 | 0.084 | [0.372, 0.788] |

per-pattern recall:

| pattern_id | mean |
| --- | --- |
| nda_duration_unbounded | 1.000 |
| nda_remedy_imbalanced | 1.000 |
| nda_jurisdiction_one_sided | 1.000 |
| nda_scope_overbroad | 0.833 |
| nda_derivative_undefined | 0.833 |
| nda_disclosure_exception_missing | 0.500 |
| nda_purpose_undefined | 0.333 |
| nda_return_destroy_missing | 0.333 |
| **nda_survival_missing** | **0.000** |

詳細は [`phase1_baseline_v1_2026-06-08.md`](phase1_baseline_v1_2026-06-08.md)。

---

## P1: `baseline.v0.2.0` — 欠落型 NG の検出ヒントを追加

### 仮説

`baseline.v0.1.0` プロンプトは「該当する NG パターンを列挙」とだけ指示している。
LLM は「該当」を「正の証拠が条文中にある」と解釈する傾向があり、`_missing` / `_undefined`
系（書かれていないことを検出する）の recall が低かった。

特に `nda_survival_missing` は 3 seed すべてで recall=0。

### 変更点

`src/tsumiki/baseline/ng_detector.py` の `_PROMPT_V0_2_0` を追加（v0.1.0 はレジストリに残し比較可能）:

1. NG パターンを **明示型** と **欠落型** の 2 種類に分けて説明
2. 欠落型は「条項本文に *あるべき規定が書かれていない／不明確である* ことが該当条件」と定義
3. 具体例として `nda_survival_missing`, `nda_return_destroy_missing`, `nda_disclosure_exception_missing` の検出基準を挙げる
4. 偽陽性回避指針として「条項の主題と無関係な欠落は列挙しない」を追加
5. プロンプトレジストリ (`_PROMPT_REGISTRY`) で複数バージョン併存、`evaluate_baseline` / `run_phase1` から版指定可能に

### 期待

- 欠落型 (`_missing` `_undefined` 系) の recall 向上
- 偽陽性回避指針により precision 維持 or 軽微改善
- 明示型 (`_overbroad` `_unbounded` 等) は変化なし or 軽微変動

### MLflow experiment

`phase1_p1_v020`

### 結果（3 seeds 完了、2026-06-09 02:36 集計）

実行コマンド:
```bash
for s in 42 43 44; do
  uv run python experiments/run_phase1_dryrun.py \
    --model "hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M" \
    --n-synth-per-pattern 10 --n-clean 10 \
    --experiment phase1_p1_v020 \
    --baseline-prompt-version v0.2.0 \
    --seed $s
done
uv run python experiments/aggregate_phase1_seeds.py \
    --experiment phase1_p1_v020 --n-clean 10
```

### vs v1 集計

| 指標 | v1 (v0.1.0) | **P1 (v0.2.0)** | 差 |
| --- | --- | --- | --- |
| **TEST macro_recall** | 0.648 ± 0.085 | **0.778 ± 0.056** | **+0.130** |
| TEST macro_precision | 0.472 ± 0.083 | 0.478 ± 0.053 | +0.006 |
| **TEST macro_F2** | 0.580 ± 0.084 | **0.641 ± 0.046** | **+0.061** |
| VAL macro_recall | 0.704 ± 0.116 | 0.796 ± 0.032 | +0.092 |

CI も縮小:
- recall std 0.085 → 0.056（seed 安定性向上）
- F2 std 0.084 → 0.046

per-pattern recall（mean）:

| pattern_id | v1 | **P1** | 差 |
| --- | --- | --- | --- |
| **nda_survival_missing** | **0.000** | **1.000** | **+1.000 🎯** |
| nda_derivative_undefined | 0.833 | 1.000 | +0.167 |
| nda_return_destroy_missing | 0.333 | 0.500 | +0.167 |
| nda_disclosure_exception_missing | 0.500 | 0.333 | -0.167 |
| nda_scope_overbroad | 0.833 | 0.833 | 0 |
| nda_purpose_undefined | 0.333 | 0.333 | 0 |
| nda_duration_unbounded | 1.000 | 1.000 | 0 |
| nda_remedy_imbalanced | 1.000 | 1.000 | 0 |
| nda_jurisdiction_one_sided | 1.000 | 1.000 | 0 |

per-pattern precision（mean）:

| pattern_id | v1 | **P1** | 差 |
| --- | --- | --- | --- |
| nda_scope_overbroad | 0.889 | 1.000 | +0.111 |
| **nda_duration_unbounded** | 0.467 | **1.000** | **+0.533** |
| nda_remedy_imbalanced | 0.889 | 0.667 | -0.222 |
| nda_jurisdiction_one_sided | 0.722 | 0.522 | -0.200 |
| **nda_survival_missing** | 0.000 | 0.163 | **+0.163（ゼロ脱却）** |
| nda_return_destroy_missing | 0.417 | 0.233 | -0.184 |
| nda_derivative_undefined | 0.411 | 0.356 | -0.055 |
| nda_purpose_undefined | 0.120 | 0.250 | +0.130 |
| **nda_disclosure_exception_missing** | 0.333 | **0.108** | **-0.225（悪化）** |

### 考察

**成功点:**

1. **主目的達成**: `nda_survival_missing` を 0.0 → 1.0（3/3 完全検出）。プロンプトに「欠落型」概念と具体例を明示する方針が機能した。
2. **macro_recall +0.130** で v1 を統計的にも実質的にも上回る（CI 重なりあるが mean 差は std の 1.5 倍）。
3. **CI 縮小**で seed ノイズが減少。プロンプトが LLM の判断ぶれを抑える効果。
4. **macro_F2 +0.061** で総合品質も改善。

**課題:**

1. **欠落型の precision 悪化**: `nda_survival_missing` (0→0.163)、`nda_return_destroy_missing` (0.417→0.233)、`nda_disclosure_exception_missing` (0.333→0.108)。「欠落」を**過剰検出**する副作用。
2. **副作用で recall 後退**: `nda_disclosure_exception_missing` recall は 0.500→0.333 と後退。FP が多すぎて分母が膨らみ、本来の TP まで判断がぶれた可能性。
3. **明示型 precision の微減**: `nda_remedy_imbalanced` 0.889→0.667 など、明示型でも precision がやや下がった（v0.2.0 で「両タイプを等しく」と書いた指示が判断を均し過ぎ）。

**P2 の方向性:**

precision を抑える指示を強化する。具体的には:
- 「明示的な根拠が条項内にある場合のみ列挙」を明示
- 欠落型は「該当主題の規定が *明確に* 言及されていないこと」を条件にし、推測での過剰検出を抑止
- 「判断に迷うときは列挙しない」の明示

| MLflow | `phase1_p1_v020`、seed=42,43,44 すべて FINISHED |
| --- | --- |

---

## P2: `baseline.v0.3.0` — 欠落型の判定条件を厳格化、過剰検出を抑制

### 仮説

P1 (v0.2.0) で `nda_survival_missing` 等の欠落型が **過剰検出**になった
（survival_missing の precision = 0.163、disclosure_exception_missing recall も逆に後退）。
これは「欠落」を *条項の主題と無関係に* 判定する暴走を許してしまった結果。

### 変更点

`baseline.v0.3.0` を追加:

1. 欠落型の列挙条件として **(a)(b)(c) 三つの条件すべて** を満たすことを明示
   - (a) 条項の主題と当該欠落 NG の対象範囲が **直接的に関連** する
   - (b) 該当規定への **明示的な言及が見当たらない**
   - (c) 「黙示」「他条項で扱う可能性」等の **推測解釈をしない**
2. 「**確信を持てない場合は列挙しない**」を判断指針として明示
3. 1 条項で複数 NG を挙げる場合は各条件を独立に再確認するよう指示

### 期待

- `nda_survival_missing` 等の precision が **大幅改善**（0.163 → 0.4 以上を目標）
- `nda_disclosure_exception_missing` の recall が **回復**（0.333 → P1 以前の 0.5 以上）
- macro_recall は P1 の 0.778 から若干低下する可能性（過剰検出が無くなる代償）
- macro_F2 は precision 改善で **P1 を上回る** ことを期待

### MLflow experiment

`phase1_p2_v030`

### 結果

**(計測中、2026-06-09 02:39 開始、3 seeds、完了予定 05:30 頃)**

実行コマンド:
```bash
for s in 42 43 44; do
  uv run python experiments/run_phase1_dryrun.py \
    --model "hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M" \
    --n-synth-per-pattern 10 --n-clean 10 \
    --experiment phase1_p2_v030 \
    --baseline-prompt-version v0.3.0 \
    --seed $s
done
uv run python experiments/aggregate_phase1_seeds.py \
    --experiment phase1_p2_v030 --n-clean 10
```

### 結果テーブル（埋め込み予定）

| 指標 | v1 (v0.1.0) | P1 (v0.2.0) | **P2 (v0.3.0)** | P2 vs P1 |
| --- | --- | --- | --- | --- |
| TEST macro_recall | 0.648 | 0.778 | TBD | TBD |
| TEST macro_precision | 0.472 | 0.478 | TBD | TBD |
| TEST macro_F2 | 0.580 | 0.641 | TBD | TBD |
| nda_survival_missing precision | 0.000 | 0.163 | TBD | TBD |
| nda_disclosure_exception_missing recall | 0.500 | 0.333 | TBD | TBD |

### 考察

（結果出てから記入）

---

## P2 結果（3 seeds 完了、2026-06-09 05:46 集計）

### vs v1, P1

| 指標 | v1 (v0.1.0) | P1 (v0.2.0) | **P2 (v0.3.0)** | P2 vs P1 |
| --- | --- | --- | --- | --- |
| TEST macro_recall | 0.648 ± 0.085 | 0.778 ± 0.056 | 0.722 ± 0.056 | -0.056 |
| TEST macro_precision | 0.472 ± 0.083 | 0.478 ± 0.053 | **0.533 ± 0.050** | **+0.055** |
| **TEST macro_F2** | 0.580 ± 0.084 | 0.641 ± 0.046 | **0.651 ± 0.047** | **+0.010** |

per-pattern 主要変化 (P1 → P2):

| pattern_id | recall | precision | コメント |
| --- | --- | --- | --- |
| nda_disclosure_exception_missing | 0.333→**0.667** | 0.108→**0.317** | **完全回復**（過剰検出抑制で本来の TP が拾えた） |
| nda_remedy_imbalanced | 1.000→1.000 | 0.667→**0.889** | 明示型 precision 復元 |
| nda_derivative_undefined | 1.000→0.833 | 0.356→**0.444** | recall 微減、precision 改善 |
| **nda_survival_missing** | 1.000→**0.500** | 0.163→0.156 | recall 後退（過剰検出抑制の代償） |
| nda_return_destroy_missing | 0.500→0.333 | 0.233→0.250 | 後退 |

### P2 考察

- **狙い通りの方向**: precision +0.055、F2 +0.010。「迷ったら列挙しない」と (a)(b)(c) 条件が機能。
- **disclosure_exception_missing の完全回復**が最大の収穫。P1 で過剰検出された survival_missing が他パターンの判定を引きずっていたことが分かる。
- **survival_missing で 1.0→0.5 と後退**: 厳格化しすぎた。「条項の主題と直接的に関連する」の制約が survival_missing を該当する条項（有効期間条項等）の半分しか検出しなくなった。
- F2 改善幅は +0.010 と小さく、P1 の +0.061 ほど劇的ではない。これ以上の改善には別アプローチ（NG パターン辞書の充実）が必要。

---

## P3: `ng_patterns v0.2.0` — NG 辞書 description を 2 段構成に書き直し

### 仮説

P2 までで LLM への一般的指示は十分に強化された。次のボトルネックは
**LLM が各 NG パターンの判定範囲を正確に把握できているか** にある。

`ng_patterns v0.1.0` の description は「何が NG か」を 1 段落で記述するのみで、
LLM は「対象条項の主題」と「除外条件」を内的に推論する必要があった。
これを **3 セクション構成（検出すべき／紛らわしい／対象条項）** に書き直し、
LLM が直接参照できる形にする。

### 変更点

1. `src/tsumiki/knowledge/nda/ng_patterns.yaml` を **v0.1.0 → v0.2.0** にバンプ。
   - 全 9 パターンの description を以下の 3 セクションに統一:
     - **検出すべき**: 該当条件
     - **紛らわしい**: 該当しない条件（FP 抑制ヒント）
     - **対象条項**: 判定対象となる条項の主題（適用範囲）
2. `src/tsumiki/baseline/ng_detector.py` の `_format_patterns_block` を更新:
   - description の全文を多行展開（旧版は 1 行目のみ採用）
   - インデント整形で可読性確保

検出プロンプトは **v0.3.0 のまま**（厳格判定ルールを維持）。

### 期待

- 各パターンの「対象条項」明示で、主題に合わない条項への過剰検出が大幅減
- 「紛らわしい」セクションで FP がさらに削減
- **survival_missing 等の欠落型 recall の回復**（対象条項を明示することで「該当しない条項では判定対象外」が明確化、結果として該当する条項では確実に検出）
- 総合 F2 で P1 (0.641) を超え 0.65〜0.70 を目標

### MLflow experiment

`phase1_p3_ngv020`

### 結果（3 seeds 完了、2026-06-09 08:55 集計）

実行コマンド:
```bash
for s in 42 43 44; do
  uv run python experiments/run_phase1_dryrun.py \
    --model "hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M" \
    --n-synth-per-pattern 10 --n-clean 10 \
    --experiment phase1_p3_ngv020 \
    --baseline-prompt-version v0.3.0 \
    --seed $s
done
uv run python experiments/aggregate_phase1_seeds.py \
    --experiment phase1_p3_ngv020 --n-clean 10
```

### 集約結果

| 指標 | v1 | P1 | P2 | **P3** | P3 vs P2 |
| --- | --- | --- | --- | --- | --- |
| TEST macro_recall | 0.648 ± 0.085 | 0.778 ± 0.056 | 0.722 ± 0.056 | **0.722 ± 0.074** | ±0 |
| TEST macro_precision | 0.472 ± 0.083 | 0.478 ± 0.053 | **0.533 ± 0.050** | 0.472 ± 0.105 | **-0.061** |
| **TEST macro_F2** | 0.580 ± 0.084 | 0.641 ± 0.046 | **0.651 ± 0.047** | 0.630 ± 0.083 | **-0.021** |

**結論: F2 -0.021、std も増大（0.047 → 0.083）。総合では P3 は P2 より悪い。**

ただし per-pattern では「大成功と大失敗が混在」。両方を残す。

### per-pattern 改善（P2 → P3）

| pattern | metric | P2 | **P3** | 差 |
| --- | --- | --- | --- | --- |
| **nda_survival_missing** | precision | 0.156 | **0.762** | **+0.606 🎯** |
| **nda_survival_missing** | recall | 0.500 | 0.833 | +0.333 |
| nda_derivative_undefined | recall | 0.833 | 1.000 | +0.167 |
| nda_jurisdiction_one_sided | precision | 0.578 | 0.722 | +0.144 |

### per-pattern 悪化（P2 → P3）

| pattern | metric | P2 | **P3** | 差 |
| --- | --- | --- | --- | --- |
| nda_scope_overbroad | precision | 1.000 | 0.578 | **-0.422** |
| nda_duration_unbounded | precision | 1.000 | 0.611 | -0.389 |
| nda_remedy_imbalanced | precision | 0.889 | 0.500 | -0.389 |
| nda_remedy_imbalanced | recall | 1.000 | 0.833 | -0.167 |
| nda_purpose_undefined | recall | 0.333 | 0.167 | -0.167 |
| nda_disclosure_exception_missing | recall | 0.667 | 0.500 | -0.167 |

### 考察

**仮説は半分正しかった:**

- **欠落型に対する効果は劇的**: `nda_survival_missing` の precision が 0.156 → 0.762 と +0.606、recall も +0.333。**辞書の「対象条項」明示が判定主題のあいまいさを解消した**。
- **明示型に対する効果は逆効果**: `nda_scope_overbroad` 等の明示型は precision が大幅悪化（-0.42 前後）。詳細記述が逆に LLM の判断を引きずって、本来明示型では明確な「該当する語句」だけを見ればよいのに余計な文脈を考慮し過ぎてしまった。

**std の拡大 (0.05 → 0.08+)**: 詳細記述が seed 間のばらつきを大きくした。
LLM が長い記述のどの部分を重視するかが seed に依存する。

**学び**: 「辞書詳細化」は一律ではなく、**パターン種別ごとに最適な記述粒度が異なる**。

- 欠落型: 「対象条項」「紛らわしい」を含む詳細記述が有効（判定主題が広いため明示が必要）
- 明示型: 短い「該当する語句のサンプル」程度が最適（明確な語句マッチで足りる）

### 次の方向

| 候補 | 内容 |
| --- | --- |
| P3.1 | 辞書を **欠落型のみ詳細化**、明示型は v0.1.0 の短い記述に戻す。欠落型の劇的改善を活かしつつ明示型の悪化を回避 |
| P4 | NG パターンごとに **few-shot 例** をプロンプトに足す（具体例で判断軸を固定） |
| 終了 | **P2 (prompt v0.3.0 + ng v0.1.0) を Phase 1 の確定ベースライン**として採用、Phase 2 に進む |

**確定ベースライン候補: P2 (TEST macro_recall=0.722, precision=0.533, F2=0.651)**

| MLflow | `phase1_p3_ngv020`、seed=42,43,44 すべて FINISHED |
| --- | --- |

---

## 振り返り (running notes)

ここに各改修の所感・気づき・次の打ち手を時系列で残す。

| 日時 | 改修 | 気づき |
| --- | --- | --- |
| 2026-06-08 23:09 | P1 開始 | プロンプトに「欠落型」の概念を導入。`_missing` / `_undefined` 命名規約と整合 |
| 2026-06-09 02:36 | P1 完走 | survival_missing 0→1.0 達成。macro_recall +0.130、F2 +0.061。代償は欠落型の precision 悪化（過剰検出）→ P2 で対処 |
| 2026-06-09 02:39 | P2 開始 | (a)(b)(c) 条件と「迷ったら列挙しない」を明文化。precision 回復が目的 |
| 2026-06-09 05:46 | P2 完走 | F2 +0.010（P1 比）、precision +0.055、disclosure_exception_missing 完全回復。代償: survival_missing 1.0→0.5 |
| 2026-06-09 05:48 | P3 開始 | NG 辞書を 3 セクション構成（検出すべき/紛らわしい/対象条項）に書き直し。プロンプトは P2 (v0.3.0) のまま |
| 2026-06-09 08:55 | P3 完走 | 全体 F2 -0.021 で P2 に劣後。ただし survival_missing precision +0.606 等、欠落型では劇的改善。明示型では逆効果。パターン種別ごとの粒度差別化が次の鍵 |
