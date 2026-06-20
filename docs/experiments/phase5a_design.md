# Phase 5a 設計: 辞書 ablation で Knowledge 層の最小再利用単位を確定

本書は Phase 5a の事前設計（実行前の合格条件・variant 定義・コマンドを後出ししないため）である。
実行後の結果は別途 `phase5a_ablation_<date>.md` に記録する。

## 0. 目的と仮説

### 0.1 目的

NDA 辞書 `src/tsumiki/knowledge/nda/ng_patterns.yaml`（version 0.3.0、Phase 2 系で +0.212 を達成した辞書系列）から各構成要素を削った variant を作り、reuse paired diff への寄与を ablation で計測する。
結果を Knowledge schema 設計（`tsumiki/knowledge/schemas/` の汎用 schema 定義）の根拠とする。

### 0.2 仮説

事前仮説は固定せず開けてみる方針。ただし以下の対抗仮説を列挙する。

| 対抗仮説 | 内容 |
| --- | --- |
| H1 | description の「検出すべき」セクションが最大寄与（要点提示効果） |
| H2 | description の「対象条項」セクションが最大寄与（探索範囲を絞る効果） |
| H3 | `excerpt_examples` が最大寄与（few-shot による具体化効果） |
| H4 | `applicable_topics` が最大寄与（機械的フィルタによる FP 抑制効果） |
| H5 | 全要素が均等に効く（schema は現状維持） |

事前にどれが正しいかは決めない。結果から決める。

## 1. variant 設計

ベース辞書: `src/tsumiki/knowledge/nda/ng_patterns.yaml`（version 0.3.0）。

| variant | description: 検出すべき | description: 紛らわしい | description: 対象条項 | excerpt_examples | applicable_topics |
| --- | --- | --- | --- | --- | --- |
| V0 baseline | ◯ | ◯ | ◯ | ◯ | ◯ |
| V1 no_detect | × | ◯ | ◯ | ◯ | ◯ |
| V2 no_confusable | ◯ | × | ◯ | ◯ | ◯ |
| V3 no_target_clause | ◯ | ◯ | × | ◯ | ◯ |
| V4 no_excerpt | ◯ | ◯ | ◯ | × | ◯ |
| V5 no_topics | ◯ | ◯ | ◯ | ◯ | × |

`name` と `severity`、`references` は全 variant で残す（パターンの同一性を保つため）。
「×」は当該フィールドを空文字 / 空配列に置換する（削除しない）。

### 1.1 初期着手範囲

6 variant × (reuse + zerobase) × 1 seed = 12 ジョブはローカル qwen 14B で約 12 時間。
段階実行とする:

| 段階 | variant | 目的 |
| --- | --- | --- |
| 段階 1 | V0, V1, V2, V3 | description 3 セクションの寄与差を確定 |
| 段階 2 | V4, V5 | excerpt_examples と applicable_topics の寄与を追加確定 |

段階 1 で description 内部の寄与差が明確に分かれば、段階 2 は優先度を下げる判断ができる。

## 2. 実験条件

| 項目 | 値 |
| --- | --- |
| 実行モデル | ローカル qwen 2.5 14B Instruct Q4_K_M on ollama（カスタム `qwen25-14b-ctx8k`, num_ctx 8192） |
| LLM 接続 | OpenAI 互換、`http://localhost:11434/v1` |
| seed | 42（Phase 2 baseline v0 / Phase 4 hybrid と同条件で比較可能） |
| n_synth_per_pattern | 5 |
| 検出器 (T1) | variant 辞書を渡す |
| 修正器 (T2) reuse | variant 辞書を渡す |
| 修正器 (T2) zerobase | 辞書を渡さない（抽象指示のみ） |
| 集約スコープ | 全 9 NG パターン |
| MLflow experiment 名 | `phase5a_ablation_{variant_id}` |
| outcomes 出力先 | `docs/experiments/phase5a_outcomes/` |

各 variant で reuse / zerobase の両方を走らせる理由は Phase 4 §2.3 と同じ。辞書が変わると T1 検出器が変わり、success_rate の分母（target NG を含むサンプルでの T1 検出）が動くため、zerobase だけ使い回すと不公平比較になる。

## 3. 主指標と合格条件（実験前固定）

### 3.1 主指標

| 指標 | 用途 |
| --- | --- |
| reuse success_rate per variant | T2 修正の成功率 |
| zerobase success_rate per variant | 同 variant 下の zerobase との比較床 |
| **paired diff = reuse - zerobase** | **主指標**。各 variant の Knowledge 層の純寄与 |
| Δ paired diff = paired diff(V0) - paired diff(Vi) | 削った要素の寄与量 |
| reuse negative_transfer per variant | 副指標。要素を削った時の波及 |

### 3.2 寄与判定ルール（後出ししない）

| Δ paired diff | 判定 | schema 設計への含意 |
| --- | --- | --- |
| `≤ 0.05` | 寄与小 | schema から除外可能（軽量化候補） |
| `0.05 < Δ ≤ 0.15` | 寄与中 | schema にオプション項目として残す |
| `> 0.15` | 寄与大 | schema 必須項目 |

しきい値 0.05 / 0.15 の根拠: Phase 2 baseline v0 の paired diff +0.261 が「強く効く」相場。その 1/5 以下なら本質的に寄与なしと見なし、半分以上なら必須項目と見なすという仕分け。中間帯はオプション。

### 3.3 baseline 一致確認ゲート

V0 を最初に走らせる。V0 の paired diff が Phase 2 baseline v0 seed=42 の値（+0.261、`phase2_baseline_v0_2026-06-10.md` 参照）と ±0.05 以内で一致すれば実験続行。逸脱したら ollama / モデル変更点を疑い、Phase 5a を中断して原因調査する。

## 4. 工数見積

| 段階 | 内容 | 想定時間 |
| --- | --- | --- |
| 0 | variant 辞書生成スクリプト実装 | 1〜2 時間 |
| 1 | V0〜V3 を順次走らせる | 約 8 時間（バッチ） |
| 2 | V4, V5 を走らせる（必要なら） | 約 4 時間 |
| 3 | 集約スクリプト実装 | 1 時間 |
| 4 | 結果記述 `phase5a_ablation_<date>.md` | 1〜2 時間 |

合計 約 15〜18 時間（夜間バッチ 2 晩で完了想定）。

## 5. 実装手順と再現コマンド

### 5.1 実装する追加ファイル

| パス | 役割 |
| --- | --- |
| `experiments/build_phase5a_variants.py` | `ng_patterns.yaml` から V0〜V5 の variant YAML を生成 |
| `experiments/run_phase5a_ablation.py` | 各 variant で `run_phase2_dryrun.py` 相当の reuse/zerobase 実行をループする薄いラッパ（または bash ループでも可） |
| `experiments/aggregate_phase5a.py` | outcomes JSONL を読み、variant ごとに paired diff と Δ paired diff を計算、Markdown 表に出力 |

### 5.2 再現コマンド（雛形）

```bash
# 0) variant 辞書を生成
uv run python experiments/build_phase5a_variants.py
# 出力: src/tsumiki/knowledge/nda/ng_patterns_v0_3_0_{V0..V5}.yaml

# 1) 各 variant で reuse + zerobase を走らせる
for variant in V0 V1 V2 V3; do
  LLM_PROVIDER=openai_compatible \
  LLM_BASE_URL=http://localhost:11434/v1 \
  LLM_API_KEY=ollama \
  LLM_MODEL=qwen25-14b-ctx8k \
  uv run python experiments/run_phase2_dryrun.py \
    --seeds 42 \
    --n-synth-per-pattern 5 \
    --experiment phase5a_ablation_${variant} \
    --outcomes-dir docs/experiments/phase5a_outcomes \
    --variant-suffix _${variant} \
    --ng-patterns-path src/tsumiki/knowledge/nda/ng_patterns_v0_3_0_${variant}.yaml
done

# 2) 集約
uv run python experiments/aggregate_phase5a.py \
  --outcomes-dir docs/experiments/phase5a_outcomes \
  --output docs/experiments/phase5a_ablation_$(date +%Y-%m-%d).md
```

`run_phase2_dryrun.py` が `--ng-patterns-path` と `--variant-suffix` を既に持っていることを前提とする（Phase 4 hybrid 実行時に同オプションを使った実績あり）。持っていなければ追加する。

## 6. リスクと対応

| リスク | 対応 |
| --- | --- |
| V0 が Phase 2 baseline v0 と乖離 | §3.3 ゲートで中断。ollama / モデルバージョン / 辞書 v0.2.0→v0.3.0 差を疑う（v0.3.0 は applicable_topics 追加） |
| variant 削除で synth 段階の出力がブレる | Phase 4 hybrid と同じく **variant ごとに synth + reuse + zerobase を full pipeline で走らせる**。synth は temperature=0 / seed=42 固定。辞書 description 差による synth 出力の揺れは記録に残し、reuse/zerobase の paired diff で吸収する（zerobase 側も同 variant 辞書で T1 を回すため、synth ブレは比較床にも反映される） |
| V4 no_excerpt で synth が壊れる場合 | synth は `tsumiki.data.synthesis` の挙動次第。pipeline 実行時に synth が完了しない variant があれば該当パターンを skip して記録、結果報告に明記する |
| ollama の num_ctx 不足 | カスタムモデル `qwen25-14b-ctx8k`（num_ctx 8192）を使用。Phase 4 で実績あり |
| 段階 1 結果が全て寄与大 | 段階 2 を走らせて 5 要素全体の順位を出す。schema 縮減は諦め、現状維持で Phase 5b に進む |
| 段階 1 結果が全て寄与小 | 「Phase 1〜2 で測ったのは Knowledge 層全体の効果で、個別要素は冗長」結論となる。schema は最小化（name + topics のみ等）に振る |

## 7. 成果物パスと関連

| 項目 | パス |
| --- | --- |
| 設計（本書） | `docs/experiments/phase5a_design.md` |
| 結果報告 | `docs/experiments/phase5a_ablation_<date>.md`（実行後に作成） |
| variant 辞書 | `src/tsumiki/knowledge/nda/ng_patterns_v0_3_0_V{0..5}.yaml` |
| outcomes JSONL | `docs/experiments/phase5a_outcomes/` |
| MLflow experiments | `phase5a_ablation_V{0..5}` |
| 関連報告 | [`phase2_baseline_v0_2026-06-10.md`](phase2_baseline_v0_2026-06-10.md), [`phase4_hybrid_2026-06-10.md`](phase4_hybrid_2026-06-10.md) |
| 検証計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) §10.4 |

## 8. Phase 5a 完了の定義

以下を満たした時点で Phase 5a 完了。

1. V0〜V3（最小）または V0〜V5（推奨）の paired diff が記録されている
2. V0 が Phase 2 baseline v0 と ±0.05 以内で一致している
3. 各要素の Δ paired diff が §3.2 ルールに沿って「寄与大 / 中 / 小」に分類されている
4. 分類結果が `phase5a_ablation_<date>.md` に記録され、`tsumiki/knowledge/schemas/` の汎用 schema 設計に活かす候補項目リストが出ている
