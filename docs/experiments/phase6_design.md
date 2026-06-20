# Phase 6 設計: ISO27001 監査チェックで仮説再現、examples/ 2 件目を作る

本書は Phase 6 の事前設計（実行前の合格条件・データ調達方針・対照実験条件を後出ししないため）である。
実装後の結果は別途 `phase6_e2e_<date>.md` に記録する。

## 0. 目的と位置づけ

### 0.1 目的

NDA 1 ドメインのみで成立した「目的駆動の自動構成 + 知識層再利用」を、**意味的に遠い別ドメイン (ISO27001 監査チェック)** で再現確認する。これによって OSS としての「シナリオ非依存」主張の根拠を作る。

### 0.2 位置づけ

Phase 1〜5 で NDA に閉じた検証を完了し、Phase 5c で目的駆動パイプライン全体が動作することを確認済。Phase 6 で N=2 ドメイン目を組み込み、フレームの再利用性と仮説再現性を実地確認する。Phase 7 (AgentSquare fork) と Phase 8 (発信) の前提となる検証。

### 0.3 Phase 5c で未実施だった検証項目

- generator パス（既存評価器が無い状態での LLM 自動生成 + 検証 + 承認）
- Knowledge 抽出パス（`source_type=extract`、`knowledge/extractors/` の動作）
- 同一フレーム下での 2 ドメイン並行動作

これらは Phase 6 で ISO27001 初投入時に自然に動かす。

## 1. ドメイン定義

### 1.1 ISO27001 監査チェックを選んだ理由

| 観点 | NDA との関係 |
| --- | --- |
| 意味的距離 | 法務契約 ↔ 情報セキュリティ統制で **遠い**。schema 汎化の検証に最適 |
| 構造的類似 | T1 = 不備検出、T2 = 是正案、で NDA と同型。Knowledge schema の再利用が試せる |
| データ入手 | IPA・JIPDEC・ISO/IEC 27001:2022 のオープン解説が豊富。合成しやすい |
| ライセンス | 公開ガイドラインからの抜粋と LLM 合成で、業務データに依存しない (CLAUDE.md §7 と整合) |
| 検証コスト | NDA と同じ Phase 2 runner を流用可。新規追加は Knowledge と評価器のみ |

### 1.2 T1 / T2 の定義

| タスク | 内容 |
| --- | --- |
| **T1 (検出)** | 入力された運用文書 or 統制記述から、ISO27001 統制不備パターンを検出する |
| **T2 (是正)** | T1 で検出された不備に対し、ISO27001 準拠の是正案文を生成する |

T1 の出力は **不備パターンの id 集合**（NDA の NG パターン id 集合と同型）。
T2 の出力は **是正後の統制記述文**（NDA の修正後条項と同型）。

### 1.3 不備パターン候補（暫定、Phase 6a で確定）

ISO/IEC 27001:2022 Annex A の主要 4 領域から、検証に十分な多様性と数 (9 件、NDA と同数) を選ぶ。**最終確定は Phase 6a データ・ラベル監査時**。

| pattern_id (暫定) | 統制領域 | 内容 |
| --- | --- | --- |
| iso_access_least_privilege_missing | A.5.15 アクセス制御 | 最小権限の原則が明記されていない |
| iso_access_review_missing | A.5.18 アクセス権 | アクセス権の定期見直し手順が無い |
| iso_log_retention_undefined | A.8.15 ログ取得 | ログの保持期間・改ざん防止策が不明確 |
| iso_backup_test_missing | A.8.13 情報のバックアップ | バックアップは定義されているが復元テストが規定されていない |
| iso_incident_response_plan_missing | A.5.24 情報セキュリティインシデント | インシデント対応の手順・連絡網が未整備 |
| iso_supplier_risk_assessment_missing | A.5.19 供給者関係 | 供給者のセキュリティリスク評価が運用に組み込まれていない |
| iso_data_classification_missing | A.5.12 情報の分類 | 情報資産の機密区分が定義されていない |
| iso_secure_disposal_missing | A.8.10 情報の削除 | 媒体・データの安全な廃棄手順が無い |
| iso_change_management_missing | A.8.32 変更管理 | 変更管理の承認・記録手順が不明確 |

NDA の 9 NG パターン (`nda_scope_overbroad` 等) と件数を揃え、対照実験のサンプル数を Phase 2 と整合させる。

## 2. データ調達

### 2.1 一次資料

| 資料 | URL or 出典 | ライセンス | 用途 |
| --- | --- | --- | --- |
| ISO/IEC 27001:2022 Annex A 統制カタログ | ISO 公式 (有料、要約は公開可) | 引用要約のみ | パターン id・名称・適用範囲の根拠 |
| IPA「中小企業の情報セキュリティ対策ガイドライン」 | IPA 公開 | 引用可（出典明示） | 統制不備の典型例と是正案 |
| IPA「ISMS構築事例集」 | IPA 公開 | 同上 | clean clauses の元になる「整備された統制記述」 |
| JIPDEC ISMS 関連ガイダンス | JIPDEC 公開 | 同上 | 統制範囲の語彙、確認ポイント |
| 各種 ISMS 公開規程テンプレート（大学・自治体等） | 各 web | 公開時点で再利用可 | 統制記述文の文体・構成 |

### 2.2 合成方針

NDA Phase 0〜1 と同じく **合成データ駆動** で進める。

| データ種別 | 数 | 生成方法 |
| --- | --- | --- |
| clean clauses (clauses_iso27001.jsonl) | ≥ 10 件 | 公開規程テンプレートから「正しく書かれた統制記述文」を抜粋 or LLM で要約 |
| synth NG samples | pattern × n_synth_per_pattern | NDA と同じ `synthesize_sample` を流用。clean に NG パターン description を注入して欠落版を生成 |

NDA 同様 `n_synth_per_pattern=5` で計 45 サンプルを目安。

### 2.3 コミット可否（CLAUDE.md §7 と整合）

| ファイル | 場所 | コミット |
| --- | --- | --- |
| 一次資料の元 PDF / 規程 | `data/raw/iso27001/<source_id>/` | **しない** (CLAUDE.md §7) |
| clean clauses 抽出スクリプト | `experiments/build_iso27001_clean_clauses.py` | する |
| 生成された clean clauses JSONL | `data/processed/clauses_iso27001.jsonl` | **しない** (`data/processed/` も .gitignore で除外済み) |
| Knowledge スキル (Markdown) | `src/tsumiki/knowledge/skills/iso27001/audit_findings/*.md` | する（公開資料からの抽象化された統制不備パターンのみ） |
| 評価器 (流用 or 新規) | `src/tsumiki/eval/generated/iso27001/...` | する |
| 結果報告 | `docs/experiments/phase6_e2e_<date>.md` | する |
| 試走で生まれた outcomes JSONL | `docs/experiments/phase6_outcomes/` | する（合成データの結果集計、業務データを含まない） |

Knowledge スキルに記載する内容は「公開ガイドラインから抽象化された統制不備パターン」のみとし、特定企業の運用情報や元規程の一字一句は含めない。

## 3. Knowledge 層構築

### 3.1 schema 流用

Phase 5a で確定した Knowledge schema をそのまま使う。フィールド名は NDA と同一:

| フィールド | 内容 | NDA との対応 |
| --- | --- | --- |
| `id` | `iso_*` のスネークケース | 同型 |
| `name` | 統制不備の日本語名 | 同型 |
| `description.対象条項` | どの統制条項が判定対象か | NDA の「対象条項」と同形式 |
| `description.検出すべき` | 不備として拾うべき内容 | 同 |
| `description.紛らわしい` | 検出から除外すべき正常パターン | 同 |
| `excerpt_examples` | 不備の典型表現 | 同 |
| `applicable_topics` | 統制領域の語彙 id (`access`, `logging`, `backup` 等) | 同 |
| `severity` | high/medium/low | 同 |
| `references` | ISO 統制番号、IPA ガイドライン参照 | 同 |

Phase 5b の Agent Skills 形式 (Markdown) で書く。フロントマター必須キー: `id, name, domain (=iso27001), schema_version`。

### 3.2 topics 語彙 (暫定)

| topic id | 名称 |
| --- | --- |
| access | アクセス制御 |
| logging | ログ取得・監視 |
| backup | バックアップ・復旧 |
| incident | インシデント対応 |
| supplier | 供給者・委託先 |
| classification | 情報分類 |
| disposal | 安全な廃棄 |
| change | 変更管理 |
| other | その他 |

### 3.3 出力先

`src/tsumiki/knowledge/skills/iso27001/audit_findings/`

- `<pattern_id>.md` 9 ファイル
- `_index.yaml`
- `topics.yaml`

## 4. 主指標と合格条件（実験前固定）

### 4.1 主指標（NDA と同じ枠組み）

| 指標 | 用途 |
| --- | --- |
| reuse success_rate | T2 (是正案) の成功率 |
| zerobase success_rate | 同条件下の対照群 |
| **paired diff = reuse - zerobase** | **主指標**。Knowledge 層の純寄与 |
| reuse negative_transfer | 副指標。target 外不備の波及 |
| zerobase negative_transfer | 同 |
| 評価器流用率 | NDA `modification_success_v1` が ISO27001 でも流用候補に上がるか |

### 4.2 合格条件（後出ししない）

| ゲート | 条件 |
| --- | --- |
| データ・ラベル監査 | clean clauses ≥ 10 件、9 NG パターンが揃い、ラベル付与基準が一貫している |
| Knowledge 層 | Agent Skills 9 ファイル + index + topics が生成され、`load_ng_patterns_auto` で読み込める |
| 評価器パス | (a) NDA 評価器 `modification_success_v1` が ISO27001 で流用 exact_match で見つかる、または (b) 流用不可なら generator が新規生成し verify を通過して保存 |
| **reuse paired diff** | **> 0**（NDA の +0.261 と同水準を期待しないが、**正の寄与** が観測されれば仮説再現） |
| 真の negative_transfer | reuse - zerobase < 0.10 程度（NDA Phase 2 人手レビュー結果と同水準） |
| 同一フレーム動作 | `examples/nda/` の Phase 5c 再現と `examples/iso27001/` の Phase 6 試走が同一 `runner/e2e.py` で完了する |

### 4.3 評価器流用の事前予想

ISO27001 の TaskSpec が `task_class=detect_and_modify`、`outputs=[findings, modified_document]` を返す場合、NDA 評価器 `modification_success_v1` の `input_signature` と一致する可能性が高い。

- 流用される場合: outcomes JSONL の構造 (`target_removed`, `new_ng_introduced`, `truth_pattern_ids`, `detected_after`) が同じため、評価器の `evaluate(outcomes)` がそのまま動く
- 流用されない場合: parser の `task_class` や outputs が NDA と異なれば generator パスへ。生成された評価器の verify を通すのが合格条件 (b)

どちらでも合格条件は揃う。Phase 5c で未実施の generator パスを観測できるのは流用されない場合のため、Phase 6 はどちらが起きてもフレームの自信を得る。

## 5. 工数見積

| 段階 | 内容 | 想定時間 |
| --- | --- | --- |
| 6a データ・ラベル監査 | 9 NG パターン確定、clean clauses ≥ 10 件、ラベル基準書 | 1〜2 日 |
| 6b Knowledge 層 (Agent Skills) | スキル 9 ファイル + index + topics 手書き | 2〜3 日 |
| 6c clean clauses 抽出スクリプト | `experiments/build_iso27001_clean_clauses.py` | 半日 |
| 6d 評価器整備 | 流用テスト + 必要なら generator パスの動作確認 | 半日 |
| 6e 試走 (run_e2e で ISO27001) | seed=42 で synth + reuse + zerobase | 約 2 時間 (ollama) |
| 6f 結果記述と判定 | `phase6_e2e_<date>.md` | 半日 |
| 6g (必要なら) NDA との同時再現 | Phase 5c を再走し、両ドメインが同フレームで動くことを確認 | 約 2 時間 |

合計 約 7〜9 日 + ollama 試走 4 時間。

## 6. 実行手順と再現コマンド (雛形)

### 6.1 0) Knowledge 層整備

```bash
# 手作業で src/tsumiki/knowledge/skills/iso27001/audit_findings/*.md と _index.yaml, topics.yaml を作成
ls src/tsumiki/knowledge/skills/iso27001/audit_findings/
```

### 6.2 1) clean clauses 抽出

```bash
uv run python experiments/build_iso27001_clean_clauses.py \
  --source data/raw/iso27001/<source_id>/ \
  --output data/processed/clauses_iso27001.jsonl
```

### 6.3 2) 試走

```bash
LLM_PROVIDER=openai_compatible \
LLM_BASE_URL=http://localhost:11434/v1 \
LLM_API_KEY=ollama \
LLM_MODEL=qwen25-14b-ctx8k \
uv run python experiments/run_phase5c_dryrun.py \
  --goal "ISO27001 の運用文書をチェックして統制不備を是正したい" \
  --knowledge-path src/tsumiki/knowledge/skills/iso27001/audit_findings \
  --experiment phase6_e2e \
  --outcomes-dir docs/experiments/phase6_outcomes \
  --evaluator-root src/tsumiki/eval/generated
```

`run_phase5c_dryrun.py` は CleanClause を `data/processed/nda_clean_clauses.jsonl` から読む実装になっている。Phase 6 では `CLEAN_JSONL` をデフォルトで切り替えるか、`--clean-jsonl` 引数を追加する。実装時に決定。

### 6.4 3) 結果集約

```bash
# aggregate_phase5a.py を流用 (variants=V0 として呼ぶ)
uv run python experiments/aggregate_phase5a.py \
  --outcomes-dir docs/experiments/phase6_outcomes \
  --seed 42 \
  --variants V0 \
  --baseline-paired-diff 0.261
```

ISO27001 では baseline は無いので `--baseline-paired-diff` は参考値。paired diff > 0 が出るかが本質。

## 7. リスクと対応

| リスク | 対応 |
| --- | --- |
| パターン定義が著作権で再配布不可 | 公開ガイドラインからの抽象化のみ採用、原文一字引用は避ける |
| clean clauses が実運用と乖離 | Phase 6a で複数公開規程テンプレートをサンプリングし多様性を確保 |
| parser が ISO27001 で task_class を誤判定 | Phase 5c で実装した動詞ガイドが効くはず。失敗時は parser プロンプト v2 を起こす |
| NDA 評価器が流用されない | 設計 §4.3 の通り generator パスを Phase 5c 未実施テストとして実走 |
| paired diff > 0 が出ない | §5.4 計画書「ゼロベースと差が無い → 明確な結論」に従い、報告書に「ISO27001 では再利用が成立しなかった」と記録。事後検証で原因（schema 表現か、ドメイン構造か）を分析 |
| ISO27001 で detector の grammar parse error が多発 | Phase 5a で detector skip 処理を追加済（`phase2.py:131-145`）。NDA と同じ skip ログが出る前提 |
| ollama context size 不足 | NDA 同様 `qwen25-14b-ctx8k`（num_ctx 8192）を使う |

## 8. Phase 7 への申し送り

Phase 6 完了後、`examples/nda/` と `examples/iso27001/` の 2 ドメインが同じ `tsumiki/` パッケージで動くことが確認できる。これを **Phase 7 で AgentSquare fork に組み込む** ときの根拠とする。

- AgentSquare のモジュール探索を Policy 層に置き換える際、Knowledge / Tool / Evaluator は Phase 6 までで確立した形をそのまま使う
- `examples/` 配下の構造（`clean_clauses.jsonl`、`knowledge/skills/`、`eval/generated/`）を OSS の使い方ガイドとして整える

## 9. 関連

| 項目 | パス |
| --- | --- |
| 設計（本書） | `docs/experiments/phase6_design.md` |
| 結果報告 | `docs/experiments/phase6_e2e_<date>.md`（実行後に作成） |
| Phase 5a 結果（Knowledge schema 確定） | [`phase5a_ablation_2026-06-19.md`](phase5a_ablation_2026-06-19.md) |
| Phase 5b 結果（Agent Skills 等価性） | [`phase5b_skills_2026-06-19.md`](phase5b_skills_2026-06-19.md) |
| Phase 5c 結果（目的駆動 E2E） | [`phase5c_e2e_2026-06-19.md`](phase5c_e2e_2026-06-19.md) |
| 計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) §10 |

## 10. Phase 6 完了の定義

以下を満たした時点で Phase 6 完了。

1. ISO27001 の 9 NG パターン確定、Knowledge スキル 9 ファイル + index + topics が `src/tsumiki/knowledge/skills/iso27001/audit_findings/` に揃う
2. clean clauses ≥ 10 件が `data/processed/clauses_iso27001.jsonl` に存在
3. `run_phase5c_dryrun.py` 系で ISO27001 を end-to-end 実行できる
4. 評価器パスで (a) 流用、または (b) 新規生成 + verify 通過 + 保存 のいずれかが成立
5. reuse paired diff > 0 か、もしくは「成立しなかった」結論が報告書に記録される
6. 同一フレーム下で NDA Phase 5c の再現が壊れていないことを確認 (リグレッション)
7. `phase6_e2e_<date>.md` に結果と Phase 7 への申し送りが記録される
