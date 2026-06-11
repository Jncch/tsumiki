# Phase 3 頑健性: 言い換えプロンプト試験（seed=42, 2026-06-10）

検証計画書 §5.2 Phase 3 のゲート: 「タスク記述の言い換え・シード変更で再実行し安定性を確認」。
シード変更は本走 (seed 42/43/44) で既に確認済み。本ドキュメントは **タスク記述（プロンプト）の言い換え** に対する安定性を測る。

## 0. 設計

| 項目 | 値 |
| --- | --- |
| seed | 42（再現のため固定） |
| プロンプト v0.1.0 | Phase 2 ベースライン v0 で使用したオリジナル |
| プロンプト v0.1.1 | 同意味・別表現の言い換え版 |
| 言い換え方針 | 「あなたは~担当です」→「次の業務を担当してください」、見出し記号 `#` → `【】`、「制約」→「守るべき条件」等。意味と入力スロットは保つ。 |
| サンプル | seed=42 の n_synth_per_pattern=5（40〜45 件） |
| モデル / 評価条件 | Phase 2 ベースライン v0 と同一 (qwen2.5 14B Q4_K_M, temperature=0) |
| T1 検出器 | Phase 1 P2 ベースライン (v0.3.0) |

## 1. 主要指標の比較

### 1.1 reuse variant

| 指標 | v0.1.0 | v0.1.1 | 差 (v0.1.1 - v0.1.0) |
| --- | --- | --- | --- |
| n_samples | 40 | 44 | +4 |
| success_rate | 0.550 | 0.455 | -0.095 |
| negative_transfer_rate | 0.700 | 0.523 | -0.177 |

### 1.2 zerobase variant

| 指標 | v0.1.0 | v0.1.1 | 差 (v0.1.1 - v0.1.0) |
| --- | --- | --- | --- |
| n_samples | 45 | 45 | +0 |
| success_rate | 0.289 | 0.289 | +0.000 |
| negative_transfer_rate | 0.444 | 0.556 | +0.111 |

### 1.3 paired diff (reuse - zerobase)

再利用の優位性 (success_rate ベース) が言い換えで保たれるか確認:

| 指標 | v0.1.0 | v0.1.1 |
| --- | --- | --- |
| paired diff (success_rate) | +0.261 | +0.166 |

## 2. パターン別 success_rate 比較

### 2.1 reuse

| pattern_id | v0.1.0 | v0.1.1 | 差 |
| --- | --- | --- | --- |
| nda_derivative_undefined | 0.250 | 0.000 | -0.250 |
| nda_disclosure_exception_missing | 1.000 | 0.600 | -0.400 |
| nda_duration_unbounded | 0.750 | 0.800 | +0.050 |
| nda_jurisdiction_one_sided | 1.000 | 0.500 | -0.500 |
| nda_purpose_undefined | 0.500 | 0.600 | +0.100 |
| nda_remedy_imbalanced | 0.600 | 0.400 | -0.200 |
| nda_return_destroy_missing | 0.200 | 0.200 | +0.000 |
| nda_scope_overbroad | 0.400 | 0.400 | +0.000 |
| nda_survival_missing | 0.250 | 0.600 | +0.350 |

### 2.2 zerobase

| pattern_id | v0.1.0 | v0.1.1 | 差 |
| --- | --- | --- | --- |
| nda_derivative_undefined | 0.000 | 0.200 | +0.200 |
| nda_disclosure_exception_missing | 0.600 | 0.400 | -0.200 |
| nda_duration_unbounded | 0.600 | 0.200 | -0.400 |
| nda_jurisdiction_one_sided | 0.200 | 0.400 | +0.200 |
| nda_purpose_undefined | 0.400 | 0.200 | -0.200 |
| nda_remedy_imbalanced | 0.400 | 0.400 | +0.000 |
| nda_return_destroy_missing | 0.000 | 0.200 | +0.200 |
| nda_scope_overbroad | 0.000 | 0.000 | +0.000 |
| nda_survival_missing | 0.400 | 0.600 | +0.200 |

## 3. 安定性判定

| 指標 | reuse 変化 | zerobase 変化 | コメント |
| --- | --- | --- | --- |
| success_rate | -0.095 | ±0.000 | reuse は ±0.1 判定基準にぎりぎり収まる。zerobase は完全安定 |
| negative_transfer_rate | -0.177 | +0.111 | T1 検出器 FP が支配的（[人手レビュー](phase2_negative_transfer_review_results_2026-06-10.md)で 81.5% が FP と判定済み）。負の転移指標の変化は本質的でない |
| paired diff | +0.261 → +0.166 | - | 縮小したが正方向維持、再利用優位は逆転していない |

### 3.1 per-pattern で見る reuse の脆弱性

reuse の言い換え耐性はパターン別に大きく分かれる:

| 大きく悪化（-0.2 以下） | 大きく改善（+0.2 以上） | ほぼ同等 |
| --- | --- | --- |
| nda_jurisdiction_one_sided (-0.500) | nda_survival_missing (+0.350) | nda_duration_unbounded (+0.050) |
| nda_disclosure_exception_missing (-0.400) | - | nda_purpose_undefined (+0.100) |
| nda_derivative_undefined (-0.250) | - | nda_return_destroy_missing (0.000) |
| nda_remedy_imbalanced (-0.200) | - | nda_scope_overbroad (0.000) |

→ **明示型 NG（jurisdiction、disclosure、remedy）で reuse の success_rate が大きく低下**、
**欠落型 NG（survival）で改善**。
辞書を参照する精度がプロンプト文体に敏感、特に「具体的な NG 文言の同定」が言い換えで揺らぐ。

一方 zerobase はパターンごとに +0.2 / -0.4 などばらつくが、平均で打ち消し合い ±0.000 に収まる。辞書を使わない分、プロンプト依存度が小さい。

## 4. 結論

### 4.1 頑健性ゲートの判定

| ゲート条件 | 観測 | 判定 |
| --- | --- | --- |
| reuse の success_rate 差が ±0.1 以内 | -0.095 | **△（ぎりぎり OK、要モニタ）** |
| zerobase の success_rate 差が ±0.1 以内 | ±0.000 | ✅ |
| paired diff が逆転しない | +0.261 → +0.166（正方向維持） | ✅ |

→ **Phase 3 頑健性ゲート: 「条件付き OK」**。
- 主指標 (success_rate) では reuse はぎりぎり判定基準内、zerobase は完全安定、paired diff も正方向維持。
- 仮説（知識層再利用が成立する）の **頑健性は seed=42, 1 言い換え版に対しては支持**。

### 4.2 表面化した課題（Phase 1 P4 / Phase 2 改良候補）

per-pattern 解析で reuse 側の「明示型 NG 修正がプロンプト文体に敏感」という弱点が表面化。
辞書を参照する LLM の挙動がプロンプト言い回しに依存しているため、`reuse.v0.1.1` の `【】` 区切り
スタイルでは辞書定義の「具体的 NG 文言」を引き出しにくかった可能性が高い。

改善方針:
1. **reuse プロンプトにラベル付き例示を入れる**: 辞書定義に「直すべき具体文言」を 1〜2 例添えて、文体不変な参照点を作る
2. **辞書の description 構造化**: 自由文より固定スロット (`明示型: ...` `欠落型: ...`) の方が言い換え耐性が高い可能性

### 4.3 検証全体の暫定結論

| Phase | ゲート | 判定 |
| --- | --- | --- |
| Phase 0 | データ・ラベル監査 | ✅ |
| Phase 1 | ベースライン (T1: macro_F2 = 0.651 ± 0.047) | ✅ |
| Phase 2 | 再利用優位性 (paired diff +0.212, 8/9 パターン優位、真の負の転移率 ≒ 0) | ✅ |
| Phase 3 | 頑健性 (paired diff 正方向維持、success_rate ±0.1 ぎりぎり OK) | **△→✅** |

→ **検証計画書 §5.4 合格条件 3/3 達成**。
**仮説「知識層再利用は成立する」を seed=42 における 1 ドメイン (NDA) 1 モデル (qwen2.5 14B) 1 言い換え版で支持**。

### 4.4 残作業 (Phase 3 拡張 + 別線)

| 案 | 内容 | 重要度 |
| --- | --- | --- |
| **頑健性拡大** | seed 43/44 でも v0.1.1 を走らせ、CI 付きで paired diff を確証 | 中 |
| **言い換えバリアント拡大** | v0.1.2（さらに別表現）を作り 3 種で頑健性を比較 | 中 |
| **T1 検出器 P4 設計** | 人手レビューで判明した条文範囲外検出問題への対処 | 高 |
| **別ドメイン横展開** | 業務委託契約等で T1+T2 を再構築し再利用優位を確認 | 高 |
| **クラウド強モデル確認** | CLAUDE.md §3 通り、最終結論はクラウドで再走 | 高（最終手前で） |

優先度は **「T1 検出器 P4」 ≥ 「別ドメイン横展開」 > 「頑健性拡大」**。
P4 を経て T1 の precision を上げれば、Phase 2/3 の解釈確度が向上し、頑健性 △ も自然に ✅ に固定できる可能性。

## 5. 関連

- Phase 2 ベースライン v0: [`phase2_baseline_v0_2026-06-10.md`](phase2_baseline_v0_2026-06-10.md)
- 人手レビュー結果: [`phase2_negative_transfer_review_results_2026-06-10.md`](phase2_negative_transfer_review_results_2026-06-10.md)
- v0.1.0 outcomes: [`phase2_outcomes/reuse_seed42.jsonl`](phase2_outcomes/reuse_seed42.jsonl)
- v0.1.1 outcomes: [`phase3_outcomes/reuse_v011_seed42.jsonl`](phase3_outcomes/reuse_v011_seed42.jsonl)
- 修正プロンプト定義: [`../../src/tsumiki/baseline/ng_modifier.py`](../../src/tsumiki/baseline/ng_modifier.py)
- 検証計画書 §5.2: [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md)
