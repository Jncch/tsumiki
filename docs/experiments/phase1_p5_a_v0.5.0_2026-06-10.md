# Phase 1 P5-A: 辞書 v0.3.0 + 検出プロンプト v0.5.0（applicable_topics 機械照合、2026-06-10）

P4 (v0.4.0) 廃案を受け、辞書を構造化（applicable_topics）してプロンプト側で機械的に
主題照合する案 P5-A を試した結果。

> **結論**: precision -0.204、macro_F2 -0.209 で両確定基準を**大幅に下回り廃案**。
> `DETECTION_PROMPT_VERSION_LATEST` は v0.3.0 のまま維持。
> 次の P6 案（または T1 改良の打ち切り判断）を §6 で提案。

## 0. P5-A の設計

| 要素 | 内容 |
| --- | --- |
| **辞書 v0.3.0** | `topics` 語彙 13 種を導入、各 NG パターンに `applicable_topics` フィールドを追加 |
| **トピック語彙** | definition / purpose / secrecy / disclosure_exception / intellectual_property / deliverable / liability / jurisdiction / duration / survival / return_destroy / confirmation / other（13 種） |
| **プロンプト v0.5.0** | (1) 条文の主題を語彙から 1 つだけ判定、(2) パターンの `applicable_topics` に含まれないものは強制スキップ、(3) 残ったパターンに (a)(b)(c) 適用 |
| **狙い** | LLM の自然言語解釈に依存する主題判定を、機械的トピック照合に置き換え、Phase 2 で問題化した「条文範囲外への過剰検出 67%」を構造的に抑制 |

## 1. 公平比較表（TEST、seed=42、n_synth=5）

| 指標 | v0.3.0 (P2) | v0.4.0 (P4) | **v0.5.0 (P5-A)** | v0.5.0 vs v0.3.0 |
| --- | --- | --- | --- | --- |
| macro_recall | 0.556 | 0.444 | **0.333** | **-0.223** |
| macro_precision | 0.352 | 0.306 | **0.148** | **-0.204** |
| macro_F2 | 0.474 | 0.384 | **0.265** | **-0.209** |

### 1.1 確定基準判定

| 確定基準 | 観測 | 判定 |
| --- | --- | --- |
| precision +0.05 以上 | -0.204 | ❌ |
| macro_F2 -0.03 以下 | -0.209 | ❌ |

→ **P5-A 廃案**。両基準とも大幅未達。

## 2. per-pattern 比較

| pattern_id | v0.3.0 (tp/fp) | v0.5.0 (tp/fp) | コメント |
| --- | --- | --- | --- |
| nda_scope_overbroad | 1/0 | 1/1 | **FP +1 悪化** |
| nda_duration_unbounded | 0/0 | 0/1 | FP +1 悪化 |
| nda_purpose_undefined | 1/1 | 1/2 | **FP +1 悪化** |
| nda_disclosure_exception_missing | 0/3 | 0/2 | **FP -1 改善 ✅** |
| nda_remedy_imbalanced | 0/0 | 0/0 | 不変 |
| nda_jurisdiction_one_sided | 1/0 | 0/0 | **recall -1.0 致命的悪化 ❌** |
| nda_return_destroy_missing | 1/2 | 1/1 | **FP -1 改善 ✅** |
| nda_derivative_undefined | 1/2 | 0/1 | **recall -1.0 致命的悪化 ❌** |
| nda_survival_missing | 0/2 | 0/0 | **FP -2 改善 ✅** |

### 2.1 改善箇所
- disclosure_exception (-1)、return_destroy (-1)、survival (-2) で FP が削減

### 2.2 致命的悪化
- **jurisdiction の recall を完全に失った**（明示型なのに 0）
- **derivative の recall を完全に失った**（P4 でも維持できていたのに）
- scope / purpose / duration では FP が増えた

## 3. 失敗の構造分析

### 3.1 トピック判定が新たな脆弱点になった

機械的トピック照合は「正しいトピックが選ばれた前提でのみ有効」。LLM の主題判定が誤ると、
適用すべきパターンが強制スキップされ **recall を完全に失う**。

推測される失敗パターン:
- 紛争解決条項を「other」または「confirmation」と判定 → jurisdiction_one_sided が強制スキップ
- 知財条項を「intellectual_property」のみと判定 → derivative_undefined も拾うべきだったが、別のトピック誤判定で消えた可能性
- 「秘密保持義務」内に違約金など複合的な要素があると、主要トピック以外のパターンが拾えない

### 3.2 構造化の代償

v0.3.0 では LLM が自然言語的に主題を解釈して `description` の「対象条項」を読み取り、
ゆるやかに該当性を判定していた。これは過剰検出 (FP) を生む反面、recall は保たれていた。

v0.5.0 は LLM の主題判定を **1 つの選択** に強制し、それを **機械的 hard filter** にかけたため、
1 つのミスで連鎖的に recall を失う構造になった。

### 3.3 v0.4.0 (P4) vs v0.5.0 (P5-A)

| 指標 | v0.4.0 (few-shot) | v0.5.0 (機械照合) |
| --- | --- | --- |
| macro_recall | 0.444 | 0.333 |
| macro_precision | 0.306 | 0.148 |
| macro_F2 | 0.384 | 0.265 |

**v0.4.0 の方がまだ少しマシ**だが、いずれも v0.3.0 を下回る。
T1 改良路線で 2 連敗。

## 4. 仮説の見直し

### 4.1 「T1 検出器を改良すれば Phase 2 解釈確度が上がる」仮説の妥当性

Phase 2 で観測された負の転移率の高さは T1 検出器の FP 由来であることが
人手レビューで判明（[`phase2_negative_transfer_review_results_2026-06-10.md`](phase2_negative_transfer_review_results_2026-06-10.md)）。

P4 / P5-A の試行で分かったこと:
- T1 検出器の FP は **プロンプト改良では下げづらい構造的問題**
- few-shot や機械照合は、改善する箇所もあるが、別箇所で副作用を生む
- ローカル 14B モデル（qwen2.5）の能力限界が見えてきた可能性

### 4.2 検証計画書 §5.4 合格条件の再確認

人手レビュー後の判定（[`phase2_baseline_v0_2026-06-10.md`](phase2_baseline_v0_2026-06-10.md) §7）:

| 条件 | 判定 |
| --- | --- |
| コールドスタート工数削減 | ✅ |
| 最終スコアを劣化させない | ✅ |
| 負の転移が出ない | ✅ (真の値 ≒ 0、観測値は T1 FP 由来) |

**§5.4 合格条件は既に達成済み**。T1 検出器をさらに改良する必要は本筋ではなく、
人手レビューで補強済みの結論は既に十分。

## 5. v0.4.0 / v0.5.0 から得た学び

| 学び | 内容 |
| --- | --- |
| プロンプト改良の限界 | v0.3.0 を超えるのが難しい。FP の本質は LLM の自然言語理解力に起因する |
| 構造化のリスク | 機械的 hard filter は失敗 1 つで recall を連鎖的に失う |
| few-shot の振れ | 「列挙する例」「列挙しない例」の混在は判定の振れを生む |
| 辞書の構造化価値 | applicable_topics の追加自体は無駄ではない。再利用知識として有用、別経路（人手チェック、別評価器）で使える可能性 |

## 6. 次の選択肢

P4 / P5-A 2 連続の廃案を踏まえ、T1 改良路線を続けるかの判断:

| 案 | 内容 | 重要度 |
| --- | --- | --- |
| **F. T1 改良打ち切り、検証次フェーズへ** | §4.2 の通り §5.4 合格条件は既に達成済み。**別ドメイン横展開** または **クラウド強モデル確認** に進む | **高（推奨）** |
| G. P6-A: applicable_topics を強制でなくヒントに | プロンプトで「主題に近いパターンを優先するが除外はしない」。改善幅は小、構造的失敗は回避 | 中 |
| H. P6-B: T1 を 14B から 32B などより大型モデルに切替 | プロンプトでなく能力で勝負。ローカル環境の制約あり | 中 |
| I. P6-C: T1 を残しつつ Phase 2 評価器側で事後フィルタ | 「conditional precision」評価器を作る。検証計画書 §7.3 のペアワイズ的アプローチに近い | 中 |
| J. P6-D: 2 段階推論（主題ごとに別 LLM call） | 構造的だが API コスト 2 倍、Phase 2/3 への波及大 | 低 |

### 6.1 推奨

**F. T1 改良打ち切り、検証次フェーズへ進む**。

理由:
1. §5.4 合格条件は人手レビューで既に達成済み
2. P4 / P5-A の試行で T1 改良の効率限界が見えた（プロンプトでは v0.3.0 を超えられない）
3. 検証計画書 §11「コミュニケーション方針」: 「不合理・非効率な案は否定する」
4. CLAUDE.md §3 で「ローカルモデルだけで結論を確定しない」「クラウド強モデルで最終確認」が指示されている → クラウド確認の方が優先度高

次に進むべき作業:
- **別ドメイン横展開**（業務委託契約等で T1+T2 を再構築し、再利用優位を別ドメインで再確認）
- **クラウド強モデルで最終確認**（CLAUDE.md §3）

## 7. 関連

- P4 評価: [`phase1_p4_v0.4.0_2026-06-10.md`](phase1_p4_v0.4.0_2026-06-10.md)
- 人手レビュー結果: [`phase2_negative_transfer_review_results_2026-06-10.md`](phase2_negative_transfer_review_results_2026-06-10.md)
- Phase 2 baseline v0（更新済み）: [`phase2_baseline_v0_2026-06-10.md`](phase2_baseline_v0_2026-06-10.md)
- Phase 3 頑健性: [`phase3_robustness_2026-06-10.md`](phase3_robustness_2026-06-10.md)
- 辞書: [`../../src/tsumiki/knowledge/nda/ng_patterns.yaml`](../../src/tsumiki/knowledge/nda/ng_patterns.yaml)
- 検出器コード: [`../../src/tsumiki/baseline/ng_detector.py`](../../src/tsumiki/baseline/ng_detector.py)
- 検証計画書: [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md)
