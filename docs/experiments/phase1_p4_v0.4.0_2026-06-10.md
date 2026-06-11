# Phase 1 P4: T1 検出器 v0.4.0（条文主題判定 + few-shot、2026-06-10）

Phase 2 人手レビュー (`phase2_negative_transfer_review_results_2026-06-10.md`) で判明した
T1 検出器の弱点 3 種に対応するため、検出プロンプトを v0.3.0 から v0.4.0 にバンプして評価。

> **結論（2026-06-10 15:11 時点）**: v0.4.0 と v0.3.0 を同条件 (seed=42, n_synth=5) で比較完了。
> precision -0.046、macro_F2 -0.090 で**両確定基準未達**。**v0.4.0 廃案**。
> 次の P5 案を §6 で提案。

## 0. v0.3.0 (P2) の課題（人手レビュー由来）

| 課題 | FP 件数（27 件中） |
| --- | --- |
| 条文範囲外への過剰検出（知財条項に派生資料、有効期間条項に開示例外など） | 多数 |
| 多段落規定の見落とし（第 5 項に行政機関開示例外があっても検出） | 多数 |
| 双方向＝標準の誤判定（「甲及び乙」を不均衡と判定） | 数件 |

特に `nda_derivative_undefined` と `nda_disclosure_exception_missing` に偏在（18/27 件 = 67%）。

## 1. v0.4.0 の改良点

| 改良 | 内容 |
| --- | --- |
| **4 ステップ構造化判定手順** | (1) 条文主題を 1 つ判定 → (2) パターンの「対象条項」とマッチング → (3) (a)(b)(c) で判定 → (4) 確信無きは列挙しない |
| **多段落汲み取り強化** | 「同一条項の別段落（例: 第 5 項）に該当規定が書かれている場合は列挙しない」を明示 |
| **few-shot 3 例** | 知財条項×derivative、秘密保持義務×disclosure、双方向×remedy の 3 大 FP パターン |
| 辞書 | v0.2.0 のまま（再利用検証への影響を最小化） |

## 2. 評価設計

| 項目 | 値 |
| --- | --- |
| ドメイン | NDA |
| モデル | qwen2.5 14B Instruct (Q4_K_M, hf.co/bartowski) |
| seed | 42（公平比較のため v0.3.0 と同一） |
| n_clean | 10 |
| n_synth_per_pattern | 5（Phase 2 と同条件） |
| 分割比 | train 0.6 / val 0.2 / test 0.2 |
| 評価指標 | NG Recall（主）、Precision、macro_F2 |
| MLflow experiment | v0.4.0: `phase1_p4_v0.4.0_seed42`、v0.3.0: `phase1_p2_v030_seed42_nsynth5` |

## 3. v0.4.0 単独の結果

```
=== outcome (elapsed 1769.1s = 29.5 min) ===
train=33  val=11  test=11
VAL  support=9  macro_recall=0.444  macro_precision=0.361  macro_F2=0.403
TEST support=9  macro_recall=0.444  macro_precision=0.306  macro_F2=0.384

=== per-pattern (TEST、support>0 のみ) ===
  nda_scope_overbroad                support=1 tp=1 fp=0 fn=0  recall=1.00
  nda_duration_unbounded             support=1 tp=0 fp=1 fn=1  recall=0.00
  nda_purpose_undefined              support=1 tp=1 fp=1 fn=0  recall=1.00
  nda_disclosure_exception_missing   support=1 tp=0 fp=0 fn=1  recall=0.00
  nda_remedy_imbalanced              support=1 tp=0 fp=0 fn=1  recall=0.00
  nda_jurisdiction_one_sided         support=1 tp=0 fp=0 fn=1  recall=0.00
  nda_return_destroy_missing         support=1 tp=1 fp=0 fn=0  recall=1.00
  nda_derivative_undefined           support=1 tp=1 fp=3 fn=0  recall=1.00
  nda_survival_missing               support=1 tp=0 fp=2 fn=1  recall=0.00
```

### 3.1 観察（v0.4.0 単独）

- **macro_F2 = 0.384** は v0.3.0 の 3 seed mean (0.651 ± 0.047) と比べ大幅に低いように見えるが、これは **seed=42 単発・n_synth=5 = TEST 11 件**のばらつき。直接比較は v0.3.0 を同条件で動かしてから行う。
- per-pattern では:
  - **明示型 NG (jurisdiction, remedy, duration) の recall が 0**: few-shot 「列挙しない」指示が効きすぎて recall 全体が低下した可能性
  - **derivative の FP が依然多い (tp=1 fp=3)**: 改善の核がここのはずだが、まだ残存
  - **scope / return_destroy は完璧 (tp=1 fp=0)**: 想定通り動作する箇所もある

## 4. v0.3.0 同条件再走（完了）

| 項目 | 値 |
| --- | --- |
| 走行コマンド | `--baseline-prompt-version v0.3.0 --seed 42 --n-synth-per-pattern 5` |
| MLflow experiment | `phase1_p2_v030_seed42_nsynth5` |
| 開始 | 2026-06-10 14:23 |
| 完了 | 2026-06-10 15:02（所要 39.1 分） |

### 4.1 公平比較表（TEST）

| 指標 | v0.3.0 (P2) | v0.4.0 (P4) | 差 | 判定 |
| --- | --- | --- | --- | --- |
| macro_recall | 0.556 | 0.444 | **-0.112** | 大幅低下 |
| macro_precision | 0.352 | 0.306 | **-0.046** | 微減 |
| macro_F2 | 0.474 | 0.384 | **-0.090** | 大幅低下 |

### 4.2 per-pattern 比較（FP 削減と recall 損失）

| pattern_id | v0.3.0 (tp/fp) | v0.4.0 (tp/fp) | コメント |
| --- | --- | --- | --- |
| nda_scope_overbroad | 1/0 | 1/0 | 不変（完璧） |
| nda_duration_unbounded | 0/0 | 0/1 | recall=0 不変、FP +1 悪化 |
| nda_purpose_undefined | 1/1 | 1/1 | 不変 |
| nda_disclosure_exception_missing | 0/3 | 0/0 | **FP -3 改善 ✅**、recall=0 維持 |
| nda_remedy_imbalanced | 0/0 | 0/0 | recall=0 不変 |
| nda_jurisdiction_one_sided | 1/0 | 0/0 | **recall -1.0 悪化 ❌** |
| nda_return_destroy_missing | 1/2 | 1/0 | **FP -2 改善 ✅**、recall 維持 |
| nda_derivative_undefined | 1/2 | 1/3 | recall 維持、**FP +1 悪化 ❌** |
| nda_survival_missing | 0/2 | 0/2 | 不変（両方失敗） |

**FP 削減できた箇所**: disclosure (-3), return_destroy (-2) → 計 -5 件
**FP 増えた／recall 失った箇所**: derivative FP +1, jurisdiction recall -1, duration FP +1

few-shot による FP 抑制は disclosure / return_destroy で機能したが、
**最大課題だった derivative では悪化**、さらに **明示型 jurisdiction の recall を失った**。
総合では裏目に出た。

## 5. 確定基準（事前固定）

- **precision +0.05 以上 AND macro_F2 -0.03 以下** → v0.4.0 を確定
- **precision 改善が +0.05 未満、または macro_F2 が -0.03 を超えて低下** → v0.4.0 廃案、次案を検討

### 5.1 判定

| 確定基準 | 観測 | 判定 |
| --- | --- | --- |
| precision +0.05 以上 | -0.046 | ❌ |
| macro_F2 -0.03 以下 | -0.090 | ❌ |

**→ v0.4.0 廃案。`DETECTION_PROMPT_VERSION_LATEST` は v0.3.0 のまま維持。**

## 6. 結論と次の P5 案

### 6.1 v0.4.0 失敗の構造分析

| 失敗モード | 原因（仮説） |
| --- | --- |
| 明示型 jurisdiction で recall=0 | 「確信を持てない場合は列挙しない」が明示型にも作用、強すぎた |
| derivative の FP +1 悪化 | few-shot 例 1 が「主題は対象条項に含まれる。ただし…」と書いたため、LLM が「対象条項に含まれる → 列挙対象」を強く読み、判定が振れた |
| disclosure / return_destroy の FP 削減成功 | 多段落汲み取り（同一条項の別段落参照）と「列挙しない例」が機能 |

### 6.2 次の P5 候補（推奨順）

#### **P5-A: 辞書 ng_patterns v0.3.0 に `applicable_topics` 構造化フィールド追加**

各パターンに machine-readable な適用範囲タグを追加し、プロンプトで機械的に主題照合:

```yaml
- id: nda_derivative_undefined
  applicable_topics: [definition, intellectual_property, deliverable]
  applicable_topics_negative: [secrecy, jurisdiction, duration, termination]
  ...
```

プロンプトは「条文の主題を 1 つ判定 → applicable_topics と一致しないパターンは強制スキップ」。
**メリット**: 構造化情報は LLM の解釈ぶれに強い。検証計画書の「知識層改善」の趣旨にも合致。
**デメリット**: 辞書を v0.3.0 にバンプ、Phase 2 baseline v0 との連続性に注意（並列ベースラインを残す）。

#### P5-B: few-shot を「対象外（列挙しない）」例のみに絞り、明示型は recall 優先指示を別途追加

v0.4.0 の問題は「対象条項に含まれる」例文と「列挙しない」例文の混在。
- few-shot を「列挙しないケース」3 例のみにする
- 明示型の項に「明示的な誤った記載があれば必ず列挙」を強調
- 構造化 4 ステップは廃止（ばらつきの源）

**メリット**: 実装小、辞書改変なしで Phase 2 連続性維持。
**デメリット**: 改善幅が小さい可能性（v0.3.0 と微差）。

#### P5-C: 明示型と欠落型でプロンプトを完全分離（2 段階推論）

- ステップ 1: 明示型のみで判定（recall 優先）
- ステップ 2: 欠落型のみで判定（precision 優先）
**メリット**: 構造的に切り分ける。
**デメリット**: API call 2 倍、コスト・レイテンシ 2 倍。Phase 2 / 3 への影響大。

### 6.3 推奨

**P5-A から進める**。辞書構造化は CLAUDE.md §7 「鮮度管理」の自然な拡張にあたり、再利用検証の趣旨にも合致。
ただし、辞書 v0.3.0 にバンプすると Phase 2 baseline v0 との比較性が下がるため、
**v0.2.0 ベースは「Phase 2 確定ベースライン用」として並列保持** する。

### 6.4 v0.4.0 から得た学び

- few-shot は **「列挙する例」と「列挙しない例」を混ぜると判定が振れる**。次は片方に絞る
- 構造化 4 ステップは LLM が **「主題判定」段階でブレる** とその後のステップに影響、ばらつきが拡大
- FP 抑制と recall 維持は **明示型と欠落型でアプローチを分ける** べき
- これらは [`phase1_prompt_iterations.md`](phase1_prompt_iterations.md) にも追記する

## 7. 関連

- 人手レビュー結果（P4 設計の根拠）: [`phase2_negative_transfer_review_results_2026-06-10.md`](phase2_negative_transfer_review_results_2026-06-10.md)
- Phase 1 P2 (v0.3.0) ベースライン: [`phase1_baseline_v1_2026-06-08.md`](phase1_baseline_v1_2026-06-08.md)
- プロンプト改善履歴: [`phase1_prompt_iterations.md`](phase1_prompt_iterations.md)
- 検出器コード: [`../../src/tsumiki/baseline/ng_detector.py`](../../src/tsumiki/baseline/ng_detector.py)
- 検証計画書: [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md)
