# Phase 5b 設計: YAML 辞書 → Agent Skills 標準への変換

本書は Phase 5b の事前設計（実行前の合格条件・変換仕様・合格ゲートを後出ししないため）である。
実装後の結果は別途 `phase5b_skills_<date>.md` に記録する。

## 0. 目的と位置づけ

### 0.1 目的

Phase 5a で確定した Knowledge schema の必須・推奨項目を、**Agent Skills 標準（Markdown スキル）** に変換するコンバータを実装する。1 NG パターン = 1 Markdown スキル。

- Markdown のフロントマターに機械的メタデータを置き、本文に LLM が読む情報を置く
- 既存の YAML ローダと等価な情報量を保ち、変換往復で意味が失われない
- 配布可能な可搬資産として `src/tsumiki/knowledge/skills/nda/ng_patterns/` 配下に格納
- Phase 5c の `runner/e2e.py` から Agent Skills 経由でも読み込める形に整える

### 0.2 位置づけ

Phase 5a で「対象条項」が寄与大、「検出すべき」「紛らわしい」「excerpt_examples」が寄与中、「applicable_topics」が prompt v0.3.0 では dead code、と確定済み。Phase 5b はこの分類を **Markdown スキルのフロントマター / 本文の区分** に落とし込む。

Phase 6（ISO27001 横展開）以降は、新ドメインを YAML で書かずに Agent Skills を直接書く運用も想定する。

### 0.3 Phase 5a §7 申し送りの訂正

Phase 5a §7 では「フロントマター必須キー: id, name, description.target_clause」と書いたが、target_clause は **LLM に判定対象を示す長文** なので、フロントマターより本文セクションが自然。Phase 5b 設計では以下に訂正する。

| 旧（Phase 5a §7） | 新（Phase 5b 設計） |
| --- | --- |
| フロントマター必須: id, name, description.target_clause | フロントマター必須: id, name, domain |
| 本文必須: description.detect, description.confusable, excerpt_examples | 本文必須: 対象条項 / 検出すべき / 紛らわしい / 例 の 4 セクション |
| 本文末尾 YAML 省略可: applicable_topics, severity, references | フロントマター推奨: severity, applicable_topics, references, task_classes |

理由: 寄与大 (target_clause) であっても、LLM が prompt 上で読む情報は本文に置くのが Agent Skills 慣習と整合。フロントマターは機械検索・分類用に絞る。

## 1. Agent Skills 標準スキーマ

### 1.1 スキルファイル構造

```markdown
---
id: <pattern_id>                   # 必須
name: <表示名>                      # 必須
domain: <ドメイン名>                # 必須（NDA / ISO27001 等）
schema_version: 1                   # 必須
task_classes: [detect, modify]      # 推奨。このスキルが効くタスクの種類
severity: high|medium|low           # 推奨
applicable_topics: [...]            # 推奨（v0.5.0 prompt 用、v0.3.0 では参照されない）
references:                         # 推奨
  - 出典 1
  - 出典 2
last_updated: 2026-06-19             # 推奨（鮮度管理、CLAUDE.md §7）
maintainer: tsumiki                  # 任意
---

# <表示名>

## 対象条項

<どの主題の条文で判定対象になるかを示す長文。Phase 5a で寄与大>

## 検出すべき

<NG として拾うべきポイント。Phase 5a で寄与中>

## 紛らわしい

<検出から除外すべき正常パターン。Phase 5a で寄与中>

## 例

- <NG の典型例 1>
- <NG の典型例 2>
```

### 1.2 フィールドの分類根拠

| フィールド | 配置 | 根拠 |
| --- | --- | --- |
| id, name | フロントマター必須 | パターン同一性、機械検索キー |
| domain | フロントマター必須 | 流用蓄積検索（Q4=B、`domain` + `task_class` + I/O schema 一致） |
| schema_version | フロントマター必須 | 将来のスキーマ進化への備え |
| task_classes | フロントマター推奨 | 流用蓄積検索キー |
| severity | フロントマター推奨 | 表示・分類用。LLM prompt には現状未投入 |
| applicable_topics | フロントマター推奨 | v0.5.0 prompt 用。v0.3.0 では dead code（Phase 5a §4.3） |
| references | フロントマター推奨 | 鮮度管理（CLAUDE.md §7）。LLM prompt 投入はしない |
| 対象条項（本文） | 本文必須 | Phase 5a Δ +0.172（寄与大） |
| 検出すべき（本文） | 本文必須 | Phase 5a Δ +0.073（寄与中） |
| 紛らわしい（本文） | 本文必須 | Phase 5a Δ +0.083（寄与中） |
| 例（本文） | 本文必須 | Phase 5a Δ +0.098（寄与中、excerpt_examples 相当） |

## 2. 変換仕様（YAML → Markdown）

### 2.1 入力

`src/tsumiki/knowledge/nda/ng_patterns.yaml`（version 0.3.0）

### 2.2 出力

`src/tsumiki/knowledge/skills/nda/ng_patterns/<pattern_id>.md` 9 ファイル

加えて:
- `src/tsumiki/knowledge/skills/nda/ng_patterns/_index.yaml`: 全スキルのインデックス（domain, topics 語彙、スキル一覧）
- `src/tsumiki/knowledge/skills/nda/ng_patterns/topics.yaml`: topics 語彙を別ファイル化（v0.5.0 prompt 用）

### 2.3 変換ルール

| YAML 元フィールド | Markdown 行き先 |
| --- | --- |
| `version` | `_index.yaml` の `source_version` |
| `contract_type` (= domain) | フロントマター `domain` |
| `last_updated` | 全スキルの `last_updated` に複写 |
| `maintainer` | 全スキルの `maintainer` に複写 |
| `topics` | `topics.yaml` に分離 |
| `patterns[].id` | フロントマター `id` |
| `patterns[].name` | フロントマター `name`、`# <name>` 見出し |
| `patterns[].description` | 「対象条項」「検出すべき」「紛らわしい」セクション抽出 |
| `patterns[].applicable_topics` | フロントマター `applicable_topics` |
| `patterns[].excerpt_examples` | 「例」セクションに `-` 行で展開 |
| `patterns[].severity` | フロントマター `severity` |
| `patterns[].references` | フロントマター `references` |

`task_classes` は YAML に無いので、変換時のデフォルト値として `[detect, modify]` を全スキルに付与する。

### 2.4 description 分割ロジック

Phase 5a の `build_phase5a_variants.py` で実装した `split_description` を流用。3 セクションヘッダ「検出すべき:」「紛らわしい:」「対象条項:」で区切り、各セクションを Markdown の H2 見出し下に再構成する。

## 3. 逆変換（Markdown → ロード）

Phase 5c で `goal/lookup` や `knowledge/loader` から Agent Skills 形式を読む必要がある。逆変換の責務:

| パス | 機能 |
| --- | --- |
| `src/tsumiki/knowledge/skills_loader.py` | Markdown スキルディレクトリを読み、`NGPatternBook` 相当の dataclass を返す |
| - | フロントマター YAML パース → メタデータ |
| - | 本文 H2 セクション抽出 → description の 3 セクション + excerpt_examples |
| - | 既存 `NGPatternBook` と同形式の dataclass を返すので、`run_phase2_dryrun.py` がそのまま使える |

`load_ng_patterns_from_path` と同等のシグネチャで、パスがディレクトリなら Agent Skills 形式、ファイルなら YAML 形式を自動判別するファクトリ `load_ng_patterns_auto` を `src/tsumiki/knowledge/loader.py` に追加する。

## 4. 主指標と合格条件（実験前固定）

### 4.1 主指標

| 指標 | 用途 |
| --- | --- |
| 変換ファイル数 | 9 ファイル + index + topics = 11 ファイル出力 |
| 情報損失チェック | Markdown 出力を逆変換した `NGPatternBook` が元 YAML 由来と等価（id / name / description セクション / excerpt / topics / severity / references が一致） |
| **NDA paired diff（Agent Skills 経由）** | **主指標**。Agent Skills を読み込んで reuse + zerobase を seed=42 で走らせ、paired diff が +0.261 ± 0.05 内 |

### 4.2 合格条件（後出ししない）

| ゲート | 条件 |
| --- | --- |
| 変換完了 | 9 スキルファイル + `_index.yaml` + `topics.yaml` が生成される |
| 情報等価性 | 逆変換した `NGPatternBook` の各フィールドが元 YAML と完全一致（unit test で確認） |
| paired diff 一致 | Agent Skills 経由で測った NDA paired diff が +0.261 ± 0.05 内（Phase 5a V0 と一致） |
| ファイル可読性 | 生成された Markdown が VS Code / GitHub で Markdown として正常レンダリングされる |

## 5. 工数見積

| ステップ | 内容 | 想定時間 |
| --- | --- | --- |
| 1 | `experiments/build_nda_skills.py` 実装（YAML → Markdown 変換） | 2〜3 時間 |
| 2 | スキル生成と目視確認 | 1 時間 |
| 3 | `src/tsumiki/knowledge/skills_loader.py` 実装（Markdown → NGPatternBook） | 3〜4 時間 |
| 4 | `src/tsumiki/knowledge/loader.py` に `load_ng_patterns_auto` 追加 | 1 時間 |
| 5 | unit test 実装（往復の情報等価性） | 2 時間 |
| 6 | NDA で reuse + zerobase 走（ollama、約 2 時間） | 2 時間 |
| 7 | 結果記述 `phase5b_skills_2026-06-XX.md` | 1〜2 時間 |

合計 約 12〜15 時間。実装 8 時間 + 試走 2 時間 + 記述 2 時間 程度。

## 6. 実装手順と再現コマンド

### 6.1 1) 変換コマンド

```bash
uv run python experiments/build_nda_skills.py \
  --source src/tsumiki/knowledge/nda/ng_patterns.yaml \
  --output-dir src/tsumiki/knowledge/skills/nda/ng_patterns
```

### 6.2 2) 情報等価性 unit test

```bash
uv run pytest tests/knowledge/test_skills_loader.py -v
```

### 6.3 3) Agent Skills 経由の試走

`run_phase2_dryrun.py` の `--ng-patterns-path` がディレクトリも受け入れるよう拡張する（`load_ng_patterns_auto` 経由）。

```bash
LLM_PROVIDER=openai_compatible \
LLM_BASE_URL=http://localhost:11434/v1 \
LLM_API_KEY=ollama \
LLM_MODEL=qwen25-14b-ctx8k \
uv run python experiments/run_phase2_dryrun.py \
  --seeds 42 \
  --n-synth-per-pattern 5 \
  --experiment phase5b_skills_v1 \
  --outcomes-dir docs/experiments/phase5b_outcomes \
  --variant-suffix _skills_v1 \
  --ng-patterns-path src/tsumiki/knowledge/skills/nda/ng_patterns
```

### 6.4 4) 集約（既存スクリプトに集約用 mode を追加 or 新規）

aggregate_phase5a.py に `--variants` で variant を可変化済みなので、それを流用:

```bash
uv run python experiments/aggregate_phase5a.py \
  --outcomes-dir docs/experiments/phase5b_outcomes \
  --seed 42 \
  --variants skills_v1 \
  --baseline-paired-diff 0.261
```

実装の都合で variant 名は `_skills_v1` ではなく `_skills` などにして、aggregate スクリプトに変更が要らない形にする選択肢もある。実装時に決定する。

## 7. リスクと対応

| リスク | 対応 |
| --- | --- |
| description セクション抽出のロジックが ng_patterns.yaml の他パターンで壊れる | Phase 5a の `split_description` を流用、unit test で 9 パターン全件を検証 |
| Markdown 本文からの逆変換で空白・改行差で意味が変わる | 検出器は description を「strip + splitlines」で展開（`ng_detector.py:281`）するので、空白差は吸収される。ただし unit test で念のため確認 |
| paired diff が +0.261 から外れる | LLM への prompt が YAML 経由と Agent Skills 経由で文字単位で異なる可能性。差は description の組み立て順序のみのはずだが、相違が見られたら逆変換後 ng_patterns を YAML として出力して diff 比較 |
| Agent Skills 標準の方言衝突 | 本検証では Anthropic / ASDA 系で広く採用されている「YAML frontmatter + Markdown 本文」の最小サブセットを採用。`schema_version: 1` で将来の方言追従が必要なら拡張できる形にする |
| topics.yaml 分離による v0.5.0 prompt 互換性 | v0.5.0 prompt は `_format_topics_block(topics)` を使う。`load_ng_patterns_auto` が topics.yaml を読み込み、loader 側で topics を `NGPatternBook` に同梱する形にする |
| 第三者がスキルを手書きしたときの整合性 | フロントマターのスキーマを `jsonschema` で検証する `validate_skills.py` を Phase 5b では雛形として用意し、Phase 7 までに整備 |

## 8. Phase 5c 以降への申し送り

- Agent Skills 形式が tsumiki の Knowledge 層の正規フォーマットになる
- Phase 5c の `knowledge/extractors/` が出力する形式も Agent Skills 標準に合わせる
- Phase 6 ISO27001 では `src/tsumiki/knowledge/skills/iso27001/<task_class>/` 配下にスキルを蓄積。NDA と同一スキーマを使えるか実地検証
- 既存 YAML 形式（`ng_patterns.yaml`）は当面残置。`load_ng_patterns_auto` 経由で両形式を扱う

## 9. 関連

| 項目 | パス |
| --- | --- |
| 設計（本書） | `docs/experiments/phase5b_design.md` |
| 結果報告 | `docs/experiments/phase5b_skills_<date>.md`（実行後に作成） |
| Phase 5a 設計 | [`phase5a_design.md`](phase5a_design.md) |
| Phase 5a 結果 | [`phase5a_ablation_2026-06-19.md`](phase5a_ablation_2026-06-19.md) |
| Phase 5c 設計 | [`phase5c_design.md`](phase5c_design.md) |
| 計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) §10 |

## 10. Phase 5b 完了の定義

以下を満たした時点で Phase 5b 完了。

1. `experiments/build_nda_skills.py` で 9 スキル + index + topics が生成される
2. `src/tsumiki/knowledge/skills_loader.py` が Markdown ディレクトリを読み NGPatternBook 等価を返す
3. `src/tsumiki/knowledge/loader.py` の `load_ng_patterns_auto` が YAML / ディレクトリを自動判別
4. unit test が情報等価性を 9 パターン全件で確認
5. Agent Skills 経由の試走で paired diff が +0.261 ± 0.05 内
6. `phase5b_skills_<date>.md` に結果と所感が記録される
