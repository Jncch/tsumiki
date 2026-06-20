# Phase 5c 設計: 目的駆動 CLI 雛形（自然言語目的→構造化→評価器生成→ナレッジ→構成→実行・評価）

本書は Phase 5c の事前設計（実行前の合格条件・コマンド・構造を後出ししないため）である。
実行後の結果は別途 `phase5c_e2e_<date>.md` に記録する。

## 0. 目的と位置づけ

### 0.1 目的

ゴール再整理（2026-06-19 確定、Q1=C, Q2=C, Q3=B, Q4=B）を踏まえ、tsumiki の **目的駆動の自動構成パイプライン雛形** を NDA ドメインで動かす。

- 自然言語で目的を入力 → LLM が構造化スキーマに変換 → ユーザー承認
- 構造化スキーマから LLM が評価器コード（決定関数 / LLM judge）を生成 → ユーザー承認 → `eval/generated/` に蓄積
- 既存の NDA ng_patterns YAML を Phase 5a 確定 schema で読み込み、エージェントを構成し end-to-end 実行
- 結果が Phase 2 baseline v0 seed=42 と paired diff ±0.05 内で一致することを合格条件とする

### 0.2 位置づけ

Phase 5a で Knowledge schema の必須/推奨フィールドを確定済、Phase 5b で YAML → Agent Skills 標準への変換コンバータを実装済（の予定）。Phase 5c はこれらを **目的駆動セットアップの中で動かす** ことで、フレーム全体が一体で動作することを実証する。

成果物は OSS 第一弾の動作する最小サンプル。Phase 6（ISO27001 横展開）と Phase 7（AgentSquare fork 統合）の前提として位置づける。

## 1. アーキテクチャ

### 1.1 全体フロー

```
[user]
  ↓ 自然言語目的（例: 「NDA をレビューして NG 条項を直したい」）
[goal/parser]      LLM で TaskSpec に変換
  ↓ TaskSpec（task_class, domain, input/output schema, hints）
[user 確認]        YAML 表示・修正
  ↓
[eval/generator]   TaskSpec から評価器候補を流用検索 or LLM 生成
  ↓ EvaluatorSpec（決定関数コード / LLM judge プロンプト）
[user 承認]        評価器コードとテストケースを目視確認
  ↓
[eval/generated/<domain>/<task_class>/<id>/ に保存]
  ↓
[knowledge/loader] Phase 5a 確定 schema で ng_patterns を読む（or Phase 5b の Agent Skills 形式）
  ↓
[policy/compose]   役割ノード（detector, modifier）を組み立て
  ↓
[runner]           入力データを流し、エージェント実行
  ↓ outcomes
[eval/runners]     承認済み評価器で集計、MLflow に記録
  ↓
[user]             結果レポート、評価器の流用蓄積を確認
```

### 1.2 各モジュールの責務

| モジュール | 入力 | 出力 | LLM 使用 |
| --- | --- | --- | --- |
| `goal/parser` | 自然言語目的文字列 | `TaskSpec`（dataclass）+ YAML 表示 | 使用（構造化変換） |
| `goal/generator` | `TaskSpec` | `EvaluatorSpec`（コード文字列 + テストケース JSONL） | 使用（コード生成） |
| `goal/store` | 承認済み `EvaluatorSpec` | `eval/generated/<domain>/<task_class>/<id>/` 保存 | 不使用（純粋なファイル I/O） |
| `goal/lookup` | `TaskSpec` | 流用候補リスト（`domain`+`task_class`+I/O schema 一致） | 不使用（メタデータ検索） |
| `eval/core/guardrails` | LLM judge 評価器 | ペアワイズ / 3 体パネル / 人手較正のラッパ | 使用（judge 呼び出し） |
| `knowledge/loader` | YAML or Agent Skills | NGPatternBook（Phase 5a 確定 schema） | 不使用 |
| `policy/compose` | TaskSpec + NGPatternBook | 役割ノードのチェイン | 不使用（AgentSquare の薄ラッパ） |
| `runner/e2e` | 全部品 | 実行結果 outcomes JSONL | 使用（エージェント実行） |

### 1.3 TaskSpec の構造

```yaml
# goal/parser が LLM 経由で生成し、ユーザーが承認する構造化スキーマ
task_class: detect_and_modify        # 主要 5 種: detect / modify / detect_and_modify / extract / compare
domain: nda                          # 自由文字列（lookup の検索キー）
input:
  target_document:
    formats: [pdf, docx, md, txt]
    role: target                     # target / reference / rule
knowledge:
  source: existing                   # existing / extract / hybrid
  catalog_path: knowledge/skills/nda/ng_patterns/  # existing の場合
output:
  findings:
    schema: ng_findings_v1           # detect 系の出力
  modified_document:
    schema: modified_text_v1         # modify 系の出力
evaluator_hints:                     # generator への指示の足がかり
  - 検出側: target_pattern が修正後に残らない率を測りたい
  - 修正側: target 以外の NG パターンが新規発生する率（negative_transfer）も測る
```

### 1.4 EvaluatorSpec の構造

```yaml
# goal/generator が LLM で生成し、ユーザーが承認する評価器仕様
id: nda_detect_and_modify_v1
domain: nda
task_class: detect_and_modify
type: deterministic                  # deterministic / llm_judge / hybrid
input_schema:
  outcomes: list of {sample_id, target_pattern_ids, detected_after, ...}
output_metrics:
  - modification_success_rate
  - negative_transfer_rate
  - per_pattern_success
implementation: |
  # Python コード（決定関数）
  def evaluate(outcomes): ...
test_cases:
  - input: { outcomes: [...] }
    expected: { modification_success_rate: 0.55, ... }
guardrails: []                       # type=deterministic なので空
sources:
  - phase 5a で確定の Knowledge schema
  - phase 1〜4 で実装した eval/modification.py を参考
generated_at: 2026-06-19
approved_by: jncch
```

LLM judge を含む場合 (`type: llm_judge` or `hybrid`) は `guardrails` に `[pairwise, panel_3, human_calibration]` のうち必要なものが自動付与される。

## 2. 実装範囲（Phase 5c で書くもの）

| パス | 役割 | 工数感 |
| --- | --- | --- |
| `src/tsumiki/goal/__init__.py` | パッケージ初期化 | - |
| `src/tsumiki/goal/parser.py` | 自然言語 → TaskSpec 変換、YAML 表示 | 中 |
| `src/tsumiki/goal/generator.py` | TaskSpec → EvaluatorSpec 生成 | 大 |
| `src/tsumiki/goal/store.py` | EvaluatorSpec の保存 / 読み込み | 小 |
| `src/tsumiki/goal/lookup.py` | 流用蓄積検索（domain + task_class + I/O schema 一致） | 小 |
| `src/tsumiki/eval/core/guardrails.py` | LLM judge ガードレールラッパ | 中（Phase 5c では雛形のみ） |
| `src/tsumiki/eval/generated/nda/detect_and_modify/ng_recall_modification_v1/` | NDA 用の初期評価器（Phase 1〜4 既存実装からの移植） | 小 |
| `src/tsumiki/runner/e2e.py` | 目的駆動 end-to-end runner | 中 |
| `experiments/run_phase5c_dryrun.py` | NDA で end-to-end を回す試走スクリプト | 小 |
| `experiments/aggregate_phase5c.py` | 結果集約。Phase 2 baseline 一致ゲート判定 | 小 |

## 3. 主指標と合格条件（実験前固定）

### 3.1 主指標

| 指標 | 用途 |
| --- | --- |
| TaskSpec 生成成功率 | 自然言語入力が TaskSpec に変換でき、ユーザー承認できる割合 |
| EvaluatorSpec 生成成功率 | TaskSpec から評価器コードが生成でき、テストケースを通過する割合 |
| end-to-end 完了率 | パイプラインが起動から最終 outcomes まで到達した割合 |
| **NDA paired diff（生成評価器版）** | **主指標**。生成評価器で測った reuse - zerobase が、Phase 2 baseline v0 seed=42 の +0.261 と ±0.05 内で一致するか |
| 流用率（lookup hit rate） | 2 回目以降の同タスク呼び出しで、既存評価器が流用候補として提示される割合 |

### 3.2 合格条件

| ゲート | 条件 |
| --- | --- |
| TaskSpec | 3 種類の自然言語入力（「NDA をレビューしたい」「NG 条項を検出して直したい」「秘密保持契約のチェック」）すべてが同一の TaskSpec に正規化される |
| EvaluatorSpec | 生成された決定関数が `test_cases.jsonl` の期待値と一致 |
| paired diff 一致 | 生成評価器で測った NDA paired diff が +0.261 ±0.05 内 |
| 流用蓄積 | 1 回目の実行で `eval/generated/nda/detect_and_modify/<id>/` にファイル一式が保存される |
| 流用検索 | 2 回目の実行で同 TaskSpec を渡すと、保存済み評価器が流用候補として提示される |

## 4. 工数見積

| ステップ | 内容 | 想定時間 |
| --- | --- | --- |
| 1 | TaskSpec dataclass 定義、`goal/parser.py` LLM 呼び出し実装 | 4〜6 時間 |
| 2 | EvaluatorSpec dataclass 定義、`goal/generator.py` LLM 呼び出し実装 | 8〜12 時間 |
| 3 | `goal/store.py` / `goal/lookup.py` ファイル I/O 実装 | 2〜3 時間 |
| 4 | `eval/core/guardrails.py` 雛形 | 4 時間 |
| 5 | NDA 既存評価器を `eval/generated/nda/...` に移植 | 2 時間 |
| 6 | `runner/e2e.py` 実装、`run_phase5c_dryrun.py` 実装 | 6〜8 時間 |
| 7 | NDA で end-to-end を 2 回（新規 + 流用）走らせ、結果記述 | 4 時間（実行は ollama で約 2 時間） |

合計 約 30〜40 時間。週末 1〜2 回のまとまった作業時間で完了想定。

## 5. 実装手順と再現コマンド（雛形）

### 5.1 1 回目の実行（評価器が無い状態）

```bash
# 目的駆動 end-to-end の試走
uv run python experiments/run_phase5c_dryrun.py \
  --goal "NDA をレビューして NG 条項を直したい" \
  --target-document data/processed/nda_samples/sample_01.docx \
  --seeds 42 \
  --experiment phase5c_e2e_first_run \
  --auto-approve-eval false   # 評価器承認を対話で行う
```

期待される流れ:
1. TaskSpec を YAML で提示 → ユーザー OK
2. lookup が「該当評価器なし」を返す
3. EvaluatorSpec を生成、コードとテストケースを表示 → ユーザー OK
4. `eval/generated/nda/detect_and_modify/<id>/` に保存
5. ng_patterns を読み、policy/compose で detector + modifier をチェイン
6. 試走、outcomes JSONL を出力
7. 承認済み評価器で集計、Phase 2 baseline と比較

### 5.2 2 回目の実行（流用検証）

```bash
uv run python experiments/run_phase5c_dryrun.py \
  --goal "別の NDA をチェックして NG を直したい" \
  --target-document data/processed/nda_samples/sample_02.docx \
  --seeds 42 \
  --experiment phase5c_e2e_second_run \
  --auto-approve-eval false
```

期待される流れ:
1. TaskSpec を YAML で提示 → ユーザー OK
2. lookup が「既存評価器あり」を返す → 1 回目で保存した評価器を流用候補に
3. ユーザー OK で評価器再利用、新規生成はスキップ
4. 以降は 1 回目と同じ

### 5.3 paired diff 一致ゲート

```bash
uv run python experiments/aggregate_phase5c.py \
  --outcomes-dir docs/experiments/phase5c_outcomes \
  --seed 42 \
  --baseline-paired-diff 0.261 \
  --tolerance 0.05
```

## 6. リスクと対応

| リスク | 対応 |
| --- | --- |
| LLM が TaskSpec を不安定に生成 | 3 種類のパラフレーズで同一 TaskSpec が出るかを §3.2 で必須ゲートに置く。失敗時は parser のプロンプト v2 を起こす |
| 生成評価器が NDA で paired diff を再現しない | EvaluatorSpec の `implementation` を Phase 1〜4 既存実装からの「ガイド付き生成」にする（テンプレ提示 + 差分のみ生成） |
| LLM judge ガードレールの実装が肥大 | Phase 5c では雛形のみ。本格実装は Phase 6（ISO27001 で開放系評価器が必要になった時）に先送り |
| ファイルパス由来の衝突（evaluator_id 重複） | `<id>` は `<task_class>_<hash>` で機械生成、重複時はサフィックスでバージョン |
| eval/generated/ の肥大 | `meta.yaml` に `last_used_at` を持たせ、6 ヶ月不使用は deprecated タグ自動付与（Phase 5c では実装のみ、運用は Phase 6 以降） |
| 既存 NDA 評価器との互換性破壊 | Phase 1〜4 で使った API（`compute_modification_report` 等）はそのまま残し、`eval/generated/` 経由の呼び出しは薄ラッパで接続 |

## 7. Phase 5d 以降への申し送り

- Phase 5c で確立した TaskSpec / EvaluatorSpec の dataclass を Phase 6 ISO27001 でそのまま再利用できることが、フレームの汎用性主張の核
- Phase 6 で `task_class: detect_and_modify` 以外（例: `detect`, `extract`）が必要になれば、その都度 TaskSpec を拡張する
- AgentSquare fork（Phase 7）への組み込みは、Phase 5c の `runner/e2e.py` を AgentSquare の探索エンジンに置き換えることで段階的に行う

## 8. 関連

| 項目 | パス |
| --- | --- |
| 設計（本書） | `docs/experiments/phase5c_design.md` |
| 結果報告 | `docs/experiments/phase5c_e2e_<date>.md`（実行後に作成） |
| 計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) §10 |
| Phase 5a 設計 | [`phase5a_design.md`](phase5a_design.md) |
| Phase 5a 結果（Knowledge schema 確定） | [`phase5a_ablation_2026-06-19.md`](phase5a_ablation_2026-06-19.md) |

## 9. Phase 5c 完了の定義

以下を満たした時点で Phase 5c 完了。

1. `src/tsumiki/goal/` `src/tsumiki/eval/core/` `src/tsumiki/eval/generated/nda/` `src/tsumiki/runner/e2e.py` 実装
2. 1 回目の実行で TaskSpec / EvaluatorSpec が承認まで進み、`eval/generated/` に保存される
3. 1 回目の paired diff が +0.261 ±0.05 内
4. 2 回目の実行で流用候補が提示され、承認・再使用できる
5. `phase5c_e2e_<date>.md` に結果と次フェーズへの申し送りが記録される
