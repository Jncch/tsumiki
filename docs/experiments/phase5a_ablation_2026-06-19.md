# Phase 5a 辞書 ablation 結果 (seed=42)

設計: [phase5a_design.md](phase5a_design.md)

## 0. 結論

> 5 要素のうち **「対象条項」セクションが reuse の純寄与に最も効く** (Δ paired diff = +0.172、寄与大)。
> 「検出すべき」「紛らわしい」「excerpt_examples」は寄与中。
> 「applicable_topics」は **今回の検出器 prompt (v0.3.0) で prompt 上に展開されない dead code** であり、寄与判定は留保。
> NDA 汎用 schema (`tsumiki/knowledge/schemas/`) では「対象条項」を必須、3 要素を推奨、topics は別 prompt 系列で再検証とする。

### 0.1 ゲートチェック

V0 paired diff = +0.261 が Phase 2 baseline v0 seed=42 (+0.261) と **|diff| = 0.000 で完全一致**し、設計 §3.3 の baseline 一致ゲートを通過。比較条件は健全。

## 1. 主指標 (paired diff = reuse - zerobase)

| variant | 操作 | reuse SR | zerobase SR | paired diff | Δ paired diff | 寄与判定 |
| --- | --- | --- | --- | --- | --- | --- |
| V0 | 全部入り (baseline) | 0.550 | 0.289 | +0.261 | - | (baseline) |
| V1 | 「検出すべき」削除 | 0.733 | 0.545 | +0.188 | +0.073 | 寄与中 |
| V2 | 「紛らわしい」削除 | 0.556 | 0.378 | +0.178 | +0.083 | 寄与中 |
| V3 | 「対象条項」削除 | 0.556 | 0.467 | +0.089 | +0.172 | 寄与大 |
| V4 | excerpt_examples 削除 | 0.595 | 0.432 | +0.163 | +0.098 | 寄与中 |
| V5 | applicable_topics 削除 | 0.550 | 0.289 | +0.261 | +0.000 | 寄与小 |

判定ルール (設計 §3.2):
- Δ paired diff ≤ 0.05 → 寄与小 (schema から除外可)
- 0.05 < Δ ≤ 0.15 → 寄与中 (schema オプション項目)
- Δ > 0.15 → 寄与大 (schema 必須項目)

## 2. 副指標 (negative_transfer)

| variant | reuse NT | zerobase NT | NT diff |
| --- | --- | --- | --- |
| V0 | 0.700 | 0.444 | +0.256 |
| V1 | 0.800 | 0.705 | +0.095 |
| V2 | 0.733 | 0.578 | +0.156 |
| V3 | 0.689 | 0.622 | +0.067 |
| V4 | 0.667 | 0.545 | +0.121 |
| V5 | 0.700 | 0.444 | +0.256 |

## 3. per-pattern reuse success_rate

| pattern_id | V0 | V1 | V2 | V3 | V4 | V5 |
| --- | --- | --- | --- | --- | --- | --- |
| nda_derivative_undefined | 0.250 | 0.800 | 0.400 | 0.400 | 0.250 | 0.250 |
| nda_disclosure_exception_missing | 1.000 | 1.000 | 0.600 | 0.800 | 1.000 | 1.000 |
| nda_duration_unbounded | 0.750 | 1.000 | 0.800 | 0.600 | 0.800 | 0.750 |
| nda_jurisdiction_one_sided | 1.000 | 1.000 | 1.000 | 0.800 | 0.750 | 1.000 |
| nda_purpose_undefined | 0.500 | 0.800 | 1.000 | 0.400 | 0.800 | 0.500 |
| nda_remedy_imbalanced | 0.600 | 0.600 | 0.400 | 0.200 | 0.400 | 0.600 |
| nda_return_destroy_missing | 0.200 | 0.400 | 0.200 | 0.600 | 0.600 | 0.200 |
| nda_scope_overbroad | 0.400 | 0.600 | 0.400 | 1.000 | 0.400 | 0.400 |
| nda_survival_missing | 0.250 | 0.400 | 0.200 | 0.200 | 0.250 | 0.250 |

## 4. 解釈

### 4.1 「対象条項」セクションが最重要

V3 (対象条項削除) のみが Δ paired diff = +0.172 で寄与大判定。理由:

- 「対象条項」セクションは LLM に「どの主題の条文で判定対象か」を明示する制約
- これが無いと判定対象外の条文まで NG として拾い、修正後文への波及（negative_transfer）が増え、target NG 除去率（success_rate）が伸び悩む
- Phase 2 人手レビュー (`phase2_negative_transfer_review_results_2026-06-10.md`) で FP の 67 % が「条文範囲外検出」だった事実と整合的

per-pattern を見ると V3 は `nda_scope_overbroad` で reuse SR が 0.400 → 1.000 と例外的に伸びている。これは ablation の副作用で、「対象条項」を削ったことで scope の判定範囲が逆に広がり、たまたま target に当たる確率が上がった可能性。集計上の paired diff は -0.172 で寄与大判定が支配。

### 4.2 「検出すべき」削除で reuse SR が +0.183 改善した謎

V1 reuse SR = 0.733（V0 比 +0.183）、V1 zerobase SR = 0.545（V0 比 +0.256）。paired diff は縮むが、両 variant とも success_rate は改善。

解釈: 「検出すべき」セクションを削ると検出器が出力する NG の傾向が変わり、success_rate の分母（target NG を含むサンプルの T1 判定）も同時に動く。Phase 4 §2.3 で観測された「zerobase が +0.075 上がった現象」と同型。

**重要含意**: ablation は paired diff で見るべきで、各 variant の絶対値（reuse SR）だけ見ると誤解する。

### 4.3 applicable_topics は今回の prompt で dead code

V5 が V0 と modify skip 5 件まで含めて完全一致した原因は実装側にある:

- `src/tsumiki/baseline/ng_detector.py:309-322` を見ると、`applicable_topics` は **prompt v0.5.0 でのみ展開**される
- 今回の検出器 prompt は v0.3.0（`run_phase2_dryrun.py` のデフォルト）
- modifier 側は `applicable_topics` を一切参照していない
- 結果として V5 (applicable_topics 削除) は prompt 文字列が V0 と一致し、出力も一致

判定上は「寄与小」だが、解釈は **「applicable_topics が無駄」ではなく「今回の prompt 設定では prompt に出ていない」** が正確。v0.5.0 prompt 系列で別途検証する必要がある。

### 4.4 副指標 negative_transfer

NT diff (reuse - zerobase) は V0=+0.256 が最大で、辞書要素を削るほど縮小する傾向。これは「辞書による T1 検出器の感度向上が、reuse 側の修正テキストにも target 以外の NG を波及させやすくなる」副作用を示唆。Knowledge schema は「修正タスクへの波及を抑える」観点での要素選択も必要だが、本検証は detection-modification 同一辞書の前提で組まれており、修正専用辞書の分離は Phase 5c 以降の課題。

## 5. Knowledge schema 設計への含意

NDA 汎用 schema (`tsumiki/knowledge/schemas/`) は次の構造で定義する:

| フィールド | 分類 | 根拠 |
| --- | --- | --- |
| `id`, `name` | 必須 | パターン同一性 |
| `description.target_clause` | **必須** | V3 で Δ +0.172（寄与大） |
| `description.detect` | 推奨 | V1 で Δ +0.073（寄与中） |
| `description.confusable` | 推奨 | V2 で Δ +0.083（寄与中） |
| `excerpt_examples` | 推奨 | V4 で Δ +0.098（寄与中） |
| `applicable_topics` | 検証保留 | v0.3.0 prompt では prompt に出ない。v0.5.0 で別途測る |
| `severity`, `references` | オプション | Phase 5a では未測定。鮮度管理（CLAUDE.md §7）で別途必要 |

Phase 5b (Agent Skills 化) では:

- 必須項目は Markdown スキルのフロントマターに置く
- 推奨項目は本文に必ず含める
- オプション項目は本文末尾の YAML ブロックに格納し、省略可能とする

## 6. 実装上の限界

| 限界 | 内容 |
| --- | --- |
| 1 seed のみ | seed=42 のみで実施。Phase 2 baseline v0 の 3 seed CI が ±0.06 程度だったので、寄与小しきい値 0.05 は誤差範囲に近い。Δ +0.07〜+0.10 帯の「寄与中」判定はノイズの可能性が残る |
| synth が variant ごとに走る | 設計 §6 の方針通り、Phase 4 と同じ前提。synth temperature=0/seed=42 で確定的だが、辞書差で synth 出力が変わるためノイズは混入する |
| detect skip 件数の variant 差 | V1 zerobase で 1 件、V4 synth で 1 件、V4 reuse で 2 件、V5 reuse で 5 件。サンプル数差は最大 5 件で結果への影響は限定的だが、ablation 純度の観点では別途記録する |
| prompt v0.3.0 固定 | applicable_topics の真の効果は v0.5.0 prompt 系列で別途検証する必要がある |
| modifier 側の影響評価不在 | 今回は detector + modifier 両方に同じ variant 辞書を渡している。modifier 単体の寄与切り分けは Phase 5c で構造分離する際に再検討 |

## 7. Phase 5b への申し送り

- Markdown スキルの構造は §5 の分類に従う
- スキル 1 個 = NG パターン 1 個（NDA は 9 個）
- フロントマター必須キー: `id`, `name`, `description.target_clause`
- 本文必須: `description.detect`, `description.confusable`, `excerpt_examples`
- 本文末尾 YAML（省略可）: `applicable_topics`, `severity`, `references`
- 変換コンバータの検証: V0 YAML から生成した Markdown スキルを再 ingest して reuse + zerobase を走らせ、paired diff が +0.261 ± 0.05 内に収まることを Phase 5b の合格条件とする

## 8. 再現コマンド

設計 [phase5a_design.md](phase5a_design.md) §5.2 参照。本実行は 2026-06-18 〜 2026-06-19 にかけて約 12 時間で完了。途中で detector 段階の grammar parse error によるクラッシュが発生し、`src/tsumiki/runner/phase2.py` の detector 呼び出しに try/except skip を追加 (`[phase2 detect] skip`) してから V1〜V5 を再走した。

