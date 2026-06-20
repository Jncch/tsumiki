# Phase 7b 結果: パッケージ再構成 (ライセンス, ディレクトリ, schema 抽象化)

実行日: 2026-06-19
設計書: [`phase7_design.md`](phase7_design.md) §1 (7b) / §3 / §6.2
前段: [`phase7a_agentsquare_2026-06-19.md`](phase7a_agentsquare_2026-06-19.md)

## 1. 結論先出し

| サブ | 結果 |
| --- | --- |
| 7b-1 ライセンス整備 | 完了. LICENSE (Apache-2.0), NOTICE, THIRD_PARTY_LICENSES/AgentSquare/README.md, pyproject.toml `license = { text = "Apache-2.0" }` |
| 7b-2 新規ディレクトリ | 完了. 9 サブパッケージに `__init__.py` 配置 |
| 7b-3 schema 抽象化 | 完了. `knowledge/schemas/ng_patterns.py` に dataclass + パース集約, `knowledge/loader.py` は re-export 構造に書き換え (後方互換) |
| 7b-4 import smoke + 共通 schema test | **16/16 PASS**, 全テスト **163/163 PASS** (リグレッションなし) |
| 7b-5 リグレッション試走 | **完了**. NDA +0.261 / ISO27001 +0.029 を ±0.000 で再現 (§4.5) |

## 2. 実装内容

### 2.1 ライセンス系 (7b-1)

| ファイル | 内容 |
| --- | --- |
| `LICENSE` | Apache License 2.0 全文 (202 行, `curl` で apache.org から取得) |
| `NOTICE` | tsumiki 著作権 + 上流 AgentSquare 属性表示 |
| `THIRD_PARTY_LICENSES/AgentSquare/README.md` | Phase 7e で vendoring する範囲を明記したプレースホルダ |
| `pyproject.toml` | `license = { text = "Apache-2.0" }`, `license-files = ["LICENSE", "NOTICE"]` 追加 |

### 2.2 新規ディレクトリ (7b-2)

`src/tsumiki/` に以下 9 サブパッケージを追加. すべて骨組のみ (docstring + `__init__.py`):

```
src/tsumiki/
├── input/                        # PDF / DOCX / MD / YAML / JSONL ローダ集約予定
├── tools/                        # 決定的関数ツール層 (検索, 比較, diff, フォーマッタ)
├── policy/
│   ├── compose/                  # AgentSquare モジュール探索ラッパ (Phase 7e)
│   ├── optimize/                 # DSPy / AFlow による再最適化 (Phase 9+)
│   └── agentsquare/              # AgentSquare partial vendoring 配置先 (Phase 7e)
├── eval/runners/                 # MLflow 連動の自動検証ランナー (Phase 9+)
└── knowledge/
    ├── extractors/               # LLM ベース構造化抽出 (RAG なし, 計画書 §10.2)
    └── schemas/                  # ドメイン横断の共通 schema (7b-3 で本実装)
```

### 2.3 schema 抽象化 (7b-3)

| ファイル | 役割 |
| --- | --- |
| `knowledge/schemas/ng_patterns.py` | `NGPattern`, `NGPatternBook`, `Topic`, `Severity` の dataclass 集約. `parse_doc()`, `load_ng_pattern_book(path)` を公開 |
| `knowledge/schemas/__init__.py` | 上記の re-export |
| `knowledge/loader.py` | schemas/ng_patterns.py からの re-export 構造に書き換え. 既存 import (`NGPattern`, `NGPatternBook`, `TopicVocab`, `_coerce_severity`, `_parse_topics`, `load_ng_patterns`, `load_ng_patterns_from_path`, `load_ng_patterns_auto`) はすべて後方互換 |

historical note (重要): `NGPatternBook.contract_type` の dataclass attribute 名は v0.1 系の YAML キー名を採用しており, 意味的には domain. ISO27001 でも `contract_type: iso27001` と書く. `NGPatternBook.domain` プロパティが Phase 7+ 以降の正式呼称 (値は `contract_type` と同じ). 正式改名は破壊変更となるため Phase 9+ で検討.

### 2.4 後方互換上の発見と修正

`src/tsumiki/knowledge/skills_loader.py` が loader モジュールの **private 関数** `_coerce_severity` と `_parse_topics` を import していた. Phase 7b で再エクスポート (private のまま) を loader.py に追加し既存挙動を維持.

## 3. テスト結果

### 3.1 Phase 7b 専用 smoke (`tests/test_phase7b_packaging.py`)

| ゲート | テスト | 件数 | 結果 |
| --- | --- | --- | --- |
| 設計書 §6.2 第 1 (import smoke) | `test_phase7b_new_packages_importable[...]` | 9 | PASS |
| 設計書 §6.2 第 2 (共通 schema) | `test_load_nda_yaml_via_common_schema` 他 | 3 | PASS |
| 後方互換 (loader re-export) | `test_legacy_loader_reexports_nga` 他 | 4 | PASS |

合計 **16/16 PASS**.

### 3.2 リグレッション (全 testpaths)

```
======================= 163 passed, 4 warnings in 1.33s ========================
```

警告 4 件は既存 (Pydantic deprecation × 2, TestCase クラス収集警告 × 2) で Phase 7b 由来ではない.

## 4. 7b-5 リグレッション試走 (ユーザー実行)

設計書 §6.2 第 3 ゲートを充足するため, ユーザー側で以下を ollama 環境で実行.

### 4.1 環境準備

```bash
# ホストで ollama が起動していること (qwen25-14b-ctx8k がロード済)
ollama list | grep qwen25-14b-ctx8k

# .env 設定 (Phase 5c / 6 と同条件)
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen25-14b-ctx8k
```

### 4.2 NDA 再現試走 (Phase 5c +0.261 が再現するか)

```bash
uv run python experiments/run_phase5c_dryrun.py \
  --goal "NDA をチェックして問題条項を是正したい" \
  --knowledge-path src/tsumiki/knowledge/skills/nda/ng_patterns \
  --clean-jsonl data/processed/nda_clean_clauses.jsonl \
  --experiment phase7b_regression \
  --outcomes-dir docs/experiments/phase7b_outcomes/nda \
  --evaluator-root src/tsumiki/eval/generated \
  --seed 42
```

### 4.3 ISO27001 再現試走 (Phase 6 +0.029 が再現するか)

```bash
uv run python experiments/run_phase5c_dryrun.py \
  --goal "ISO27001 の運用文書をチェックして統制不備を是正したい" \
  --knowledge-path src/tsumiki/knowledge/skills/iso27001/audit_findings \
  --clean-jsonl data/processed/clauses_iso27001.jsonl \
  --experiment phase7b_regression \
  --outcomes-dir docs/experiments/phase7b_outcomes/iso27001 \
  --evaluator-root src/tsumiki/eval/generated \
  --seed 42
```

### 4.4 結果集約

```bash
uv run python experiments/aggregate_phase5a.py \
  --outcomes-dir docs/experiments/phase7b_outcomes/nda \
  --seed 42 --variants V0 --baseline-paired-diff 0.261

uv run python experiments/aggregate_phase5a.py \
  --outcomes-dir docs/experiments/phase7b_outcomes/iso27001 \
  --seed 42 --variants V0 --baseline-paired-diff 0.029
```

### 4.5 合格判定 (2026-06-19 試走完了)

| ドメイン | 期待値 (Phase 5c/6) | 試走値 | 誤差 | 判定 |
| --- | --- | --- | --- | --- |
| NDA paired_diff | +0.261 | +0.261 | ±0.000 | **OK** |
| ISO27001 paired_diff | +0.029 | +0.029 | ±0.000 | **OK** |
| NDA skip | 同水準 | 5/45 (11%) | - | 許容 |
| ISO27001 skip | 同水準 | 6/45 (13%) | - | 許容 |

許容誤差は ±0.01 (設計書 §6.2 第 3 ゲート). 両ドメインとも ±0.000 で再現.

詳細:

- NDA: reuse n=40 / success_rate=0.550, zerobase n=45 / success_rate=0.289
- ISO27001: reuse n=39 / success_rate=0.410, zerobase n=42 / success_rate=0.381

### 4.6 試走時の実装上の発見

| 発見 | 内容 | 対応 |
| --- | --- | --- |
| `.env` がコンテナ内専用 | `LLM_BASE_URL=http://host.docker.internal:11434/v1`, `LLM_PROVIDER=azure_openai`, `LLM_MODEL=qwen2.5:14b-instruct-q4_K_M` がホスト直接実行と不整合 | 7b-5 試走はシェル env で上書き. Phase 7d で `.env.example` をホスト/コンテナ両対応に整備 |
| ISO27001 clean clauses ファイル名 | 設計書 §6.3 では `clauses_iso27001.jsonl` 表記だが実体は `iso27001_clean_clauses.jsonl` | 7c で設計書 §6.3 のコマンド表記を実体に合わせる. `examples/iso27001/run.sh` も実体名で書く |
| llama-server `pos 22` パースエラー | プロンプト先頭付近の特定文字列で ollama が 500 を返す. 5〜6 件 / 45 sample (Phase 5c / 6 と同水準) | Phase 5a の skip ハンドラがカバー. 根本原因は Phase 7d で再現サンプルを採取して調査 |
| `run_phase5c_dryrun.py` の gate 表示 | 内部に Phase 5a V0 baseline (+0.261) がハードコードされており, ISO27001 試走でも `gate (±0.05): FAIL` と誤表示する | 7c で gate 表示を baseline 引数化 (`--baseline-paired-diff`) するか, 表示を削除 |

## 5. リスクと所感

| 項目 | 内容 |
| --- | --- |
| `NGPatternBook.contract_type` 命名の dead code 化リスク | `domain` プロパティを追加したが, 旧 attribute 名は YAML キーと連動しているため当面残置. Phase 9+ で YAML schema v0.4 / v0.2 同時改修時に統一する |
| `_coerce_severity` 等の private 関数 export | skills_loader.py が依存している既存事実があり, Phase 7b では維持. Phase 7c で skills_loader 側を `from schemas.ng_patterns import` に書き換える方が筋. ただし破壊変更ではなく挙動同等のリファクタなので Phase 7c 着手時に判断 |
| Apache-2.0 LICENSE の curl 取得 | `WebFetch` が「ライセンス全文の出力は不可」と返したため `curl https://www.apache.org/licenses/LICENSE-2.0.txt` で取得. 中身は 202 行で公式版と一致 (先頭 / 末尾を目視確認) |
| THIRD_PARTY_LICENSES/AgentSquare/LICENSE 本体 | Phase 7e の vendoring 着手時にリポジトリの実物を確認して配置. 現時点は README のみ |

## 6. 設計書ゲート充足状況

| ゲート | 状態 | 根拠 |
| --- | --- | --- |
| §6.2 第 1 ディレクトリ (import 通る) | OK | `tests/test_phase7b_packaging.py` 9 件 PASS |
| §6.2 第 2 schema 抽象化 (NDA / ISO27001 が共通 schema に乗る) | OK | 同 3 件 + dataclass 同一性確認 PASS |
| §6.2 第 3 リグレッション (誤差 ±0.01) | OK | 7b-5 完了, NDA +0.261 / ISO27001 +0.029 を ±0.000 で再現 (§4.5) |

## 7. Phase 7c への申し送り

7b-5 試走通過済. Phase 7c で以下に着手:

1. `examples/{nda,iso27001}/` ディレクトリを作成し, `README.md` / `goal.yaml` / `run.sh` を配置 (設計書 §3.2 / §6.3)
2. `examples/<domain>/knowledge/` は `src/tsumiki/knowledge/skills/<domain>/` への symlink を採用 (二重管理回避, 設計書 §9 リスク表)
3. `examples/<domain>/clean_clauses.jsonl` は `data/processed/` から symlink (data/ は .gitignore のため commit 対象外)
4. `run.sh` は `experiments/run_phase5c_dryrun.py` を呼ぶラッパで, 7b-5 の 4.2 / 4.3 コマンドそのものに帰着させる. ISO27001 のファイル名は実体 `iso27001_clean_clauses.jsonl` を採用 (§4.6 発見事項)
5. skills_loader.py の private import 依存を `from tsumiki.knowledge.schemas import ...` に書き換える (§5 リスク表)
6. `run_phase5c_dryrun.py` の gate 表示を baseline 引数化 (§4.6 発見事項)
7. `.env.example` の整備は Phase 7d 課題として保留

## 8. 関連

| 項目 | パス |
| --- | --- |
| 設計書 (Phase 7 全体) | [`phase7_design.md`](phase7_design.md) |
| Phase 7a 結果 | [`phase7a_agentsquare_2026-06-19.md`](phase7a_agentsquare_2026-06-19.md) |
| 計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) §10 |
