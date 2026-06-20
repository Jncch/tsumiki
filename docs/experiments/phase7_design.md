# Phase 7 設計: tsumiki パッケージ整形、AgentSquare 統合、examples/ 2 件で同一フレーム動作

本書は Phase 7 の事前設計（実行前の合格条件・統合方針・対照実験条件を後出ししないため）である。
実装後の結果は別途 `phase7_<topic>_<date>.md` に記録する。

## 0. 目的と位置づけ

### 0.1 目的

Phase 1〜6 で得た「目的駆動の自動構成 + Knowledge / Tool 層再利用」の有効性 (NDA paired diff +0.261、ISO27001 +0.029) を、**OSS として公開可能なパッケージ形態** に整形する。

具体的には以下を成立させる。

- `tsumiki/` パッケージのディレクトリ構造を計画書 §10.1 の最終形に整える
- AgentSquare をモジュール探索エンジンとして組み込み (`policy/compose/`)
- `examples/nda/` と `examples/iso27001/` が **同一の `tsumiki/` コード** で動作する
- LLM プロバイダ層 (`src/tsumiki/llm/`) を ollama / OpenAI 互換クラウド / Anthropic の 3 系統に拡張
- generator パスをクラウド GPT-5.4 で再検証し、qwen 14B で観測された生成コードの意味的品質不足が改善するか確認

### 0.2 位置づけ

Phase 6 で N=2 ドメインの仮説再現が完了し、フレームのドメイン非依存性は実地確認済 (paired diff > 0 が 2 ドメイン双方で成立)。Phase 7 はこれを **OSS リリースに耐える構造** に再編する段階。Phase 8 (Zenn Part 3/4 公開 + GitHub リポジトリ公開) の前提となる。

### 0.3 Phase 6 から引き継ぐ未解決事項

| 項目 | 内容 | Phase 7 での扱い |
| --- | --- | --- |
| generator パス品質不足 | qwen 14B で生成された評価器コードが `target_pattern_1` を文字列 literal として扱う等、意味的に壊れていた (Phase 6 §5) | Phase 7d でクラウド GPT-5.4 にて再検証 |
| ISO27001 clean clauses の合成乖離 | 10 件は手書き合成のため実規程テンプレートとの分布乖離可能性 | Phase 7 範囲外。Phase 9+ で追加サンプリング |
| 3 seed CI、人手較正 | seed=42 単発のため統計的安定性が未確認 | Phase 7 範囲外。Phase 9+ |

## 1. 工程分割 (7a〜7e)

Phase 7 は 2〜3 週の大規模フェーズ。以下のサブフェーズに分け、各サブで設計事前固定 → 実装 → 試走 → 記述のサイクルを踏む (`[[feedback-design-first-workflow]]`)。

| サブフェーズ | 内容 | 主成果物 | 想定期間 |
| --- | --- | --- | --- |
| 7a | AgentSquare 上流調査と統合方針確定 | `phase7a_agentsquare_<date>.md`、本書 §2 の確定版 | 2〜3 日 |
| 7b | `tsumiki/` パッケージ再構成 (fork なし版) | `src/tsumiki/{input,tools,policy}` 追加、`schemas/` 抽象化 | 3〜5 日 |
| 7c | `examples/{nda,iso27001}/` リファレンス整備 | `examples/` 配下のリファレンス実装、同一コード動作確証 | 2〜3 日 |
| 7d | LLM プロバイダ層拡張 + generator クラウド再検証 | `src/tsumiki/llm/` 3 系統対応、`phase7d_generator_cloud_<date>.md` | 3〜4 日 |
| 7e | AgentSquare 統合 (`policy/compose/`) | `src/tsumiki/policy/compose/`、統合ライセンス対応 | 3〜5 日 |

合計 13〜20 営業日 (計画書 §10.4 の「2〜3 週」と整合)。

## 2. AgentSquare 統合方針

### 2.1 計画書 §10.1 との解釈差分

計画書 §10.1 は "tsumiki/ AgentSquare fork ベース" と書いている。しかし Phase 5c で `goal/` が前段に立った時点で、依存関係は逆転している:

- 改定前の想定: AgentSquare をベースに knowledge/tool/eval を差し替える
- 改定後の実態 (Phase 5c 以降): `goal/` → `knowledge/` → `eval/` → `policy/` (ここで初めて AgentSquare のモジュール探索が走る) → `runner/`

つまり AgentSquare は **tsumiki の下流モジュール** であり、root ではない。fork してソースを書き換える必要は (現時点では) 無い。Phase 7a の調査結果に基づき以下のどちらかを採用する。

| 方針 | 採用条件 | 工数 |
| --- | --- | --- |
| **A. 依存ライブラリとして利用 (推奨)** | AgentSquare の公開 API が `policy/compose/` で必要な「制約付きモジュール探索」を公開している場合 | 小 |
| **B. ハードフォーク + 差分管理** | A の API が無く、本体改変が必須な場合 | 大 (上流追随コスト発生) |

**事前推奨は A**。fork するなら理由を Phase 7a 報告書に明示する。

### 2.2 AgentSquare のどのレイヤーに何を接続するか

AgentSquare のモジュール構成 (Planning / Reasoning / Tool Use / Memory) に対し、tsumiki の資産を以下に対応させる:

| AgentSquare 側 | tsumiki 側 | 接続方法 |
| --- | --- | --- |
| Planning | `goal/` (自然言語目的 → TaskSpec) | TaskSpec をモジュール探索の制約として供給 |
| Reasoning | `policy/optimize/` (DSPy / AFlow) | Phase 7e 以降の追加 (本サブは射程外) |
| Tool Use | `tools/` (検出・差分・フォーマッタ) | プラグイン規約で登録 |
| Memory | `knowledge/skills/` (Agent Skills) | スキル流用蓄積を Memory として参照 |
| Evaluator (AgentSquare 内蔵) | `eval/generated/<domain>/<task_class>/<id>/` | tsumiki 側でガードレール適用 (`eval/core/guardrails.py`) 後に AgentSquare へ渡す |

評価器流用 (CLAUDE.md §9: 評価器が無い状態で自動探索を回さない) は tsumiki 側で完結させ、AgentSquare には **承認済み評価器のみ** を渡す。AgentSquare の探索が走る前に `goal/lookup.py` で評価器流用、`goal/generator.py` + `verifier.py` で新規生成 + verify 通過、`goal/store.py` で保存、という gate を必ず通す。

### 2.3 ライセンス確認 (Phase 7a で確定)

AgentSquare (`tsinghua-fib-lab/AgentSquare`) のライセンスを確認し、tsumiki (想定 Apache-2.0 or MIT) と整合するかを Phase 7a 冒頭で確認する。fork する場合は LICENSE / NOTICE を継承。

## 3. ディレクトリ構成と差分

### 3.1 現状 (Phase 6 完了時)

```
src/tsumiki/
├── baseline/        # Phase 1 ベースライン
├── data/            # データローダ
│   └── sources/
├── eval/
│   ├── core/        # ガードレール (pairwise/panel_3/human_calibration)
│   └── generated/   # 流用蓄積 (nda, iso27001)
├── exp/             # MLflow ロガー
├── goal/            # 目的駆動 (parser/generator/verifier/store/lookup/render/specs)
├── knowledge/
│   ├── iso27001/
│   ├── nda/
│   └── skills/      # Agent Skills
├── llm/             # client.py 1 ファイル
├── runner/          # phase1.py, phase2.py, e2e.py
└── smoke/
```

### 3.2 Phase 7 完了時 (目標)

計画書 §10.1 と整合。新規追加・改名箇所のみ列挙。

```
src/tsumiki/
├── baseline/                       # 既存
├── data/                           # 既存
├── eval/
│   ├── core/                       # 既存
│   ├── generated/                  # 既存
│   └── runners/                    # 【新規】 MLflow 連動の自動検証ランナー (exp/ から分離)
├── exp/                            # 既存 (一部 eval/runners/ へ移動)
├── goal/                           # 既存
├── input/                          # 【新規】 PDF / DOCX / MD / YAML / JSONL ローダ
├── knowledge/
│   ├── extractors/                 # 【新規】 LLM ベースの構造化抽出
│   ├── schemas/                    # 【新規】 NG パターン等の共通 schema
│   ├── skills/                     # 既存
│   ├── nda/                        # 既存 (元 YAML、移行検討)
│   └── iso27001/                   # 既存 (元 YAML、移行検討)
├── llm/                            # 【拡張】 ollama / openai / anthropic の 3 系統
├── policy/                         # 【新規】
│   ├── compose/                    # 【新規】 AgentSquare モジュール探索ラッパ
│   └── optimize/                   # 【新規骨組のみ】 DSPy / AFlow (Phase 9+ で実装)
├── tools/                          # 【新規】 検索・比較・diff・フォーマッタ等
├── runner/                         # 既存
└── smoke/                          # 既存

examples/                           # 【新規】
├── nda/
│   ├── README.md
│   ├── goal.yaml                   # 自然言語目的 + TaskSpec
│   ├── knowledge/                  # NDA Agent Skills の copy or symlink
│   └── run.sh
└── iso27001/
    ├── README.md
    ├── goal.yaml
    ├── knowledge/
    └── run.sh
```

### 3.3 既存資産の扱い

| 既存パス | 扱い |
| --- | --- |
| `src/tsumiki/knowledge/nda/ng_patterns.yaml` | `knowledge/schemas/` に schema、`knowledge/skills/nda/` にスキル本体を集約。元 YAML は当面残置 |
| `src/tsumiki/knowledge/iso27001/audit_findings.yaml` | 同上 |
| `src/tsumiki/runner/phase1.py`, `phase2.py` | 残置。Phase 7 では `runner/e2e.py` を主 entry とし、phase 系は研究用 |
| `experiments/*` 大量スクリプト | 残置。examples/ への一部移植のみ実施 |
| `src/tsumiki/llm/client.py` | 拡張 (§4) |

## 4. LLM プロバイダ層拡張 (Phase 7d)

### 4.1 現状

`src/tsumiki/llm/client.py` は OpenAI 互換エンドポイント (ollama, クラウド OpenAI 互換) を base_url 切替で扱う実装。

### 4.2 拡張内容

| プロバイダ | エンドポイント | 用途 |
| --- | --- | --- |
| ollama (既存) | `http://localhost:11434/v1` (ホスト) または `host.docker.internal:11434/v1` (コンテナ内) | 開発・配管・探索ループ |
| OpenAI 互換クラウド (拡張) | `https://api.openai.com/v1` 等 | generator 再検証・最終確認 |
| Anthropic (新規) | `https://api.anthropic.com/v1` | 上限確認 (claude-opus-4-8 など) |

### 4.3 制約 (CLAUDE.md §3 と整合)

- アプリ本体から特定プロバイダ SDK を直接呼ばない
- `.env` で `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` を切替
- ollama は Metal 加速のためホスト常駐 (コンテナ内では動かさない)
- ローカルモデルだけで最終結論を確定しない (CLAUDE.md §9)

## 5. generator パスのクラウド再検証 (Phase 7d)

### 5.1 Phase 6 で観測された問題

`experiments/test_phase6_generator.py` を qwen 14B (Q4_K_M, num_ctx 8192) で走らせたところ、生成された評価器コードが意味的に壊れていた:

- `target_pattern_1` を **文字列 literal** として扱い、変数参照ではない
- 評価関数のシグネチャは合っているが本体ロジックが破綻
- verify を通過しないため store には保存されず、Phase 6 では seed 投入で回避

### 5.2 Phase 7d で確認したいこと

| 観点 | 期待 | 失敗時の判定 |
| --- | --- | --- |
| generator がクラウド GPT-5.4 (or claude-opus-4-8) で意味的に正しいコードを出力するか | 出力 → verifier 通過 → store に保存 | 失敗時は generator プロンプトの修正 or 出力スキーマ強制 (function calling 化) を検討 |
| ガードレール (`eval/core/guardrails.py`) を含む評価器が生成できるか | LLM judge を含む場合は pairwise / panel_3 / human_calibration のいずれかが必ず付く | 失敗時は `EvaluatorSpec.__post_init__` のバリデーション強化 |

### 5.3 試走シナリオ

- NDA `detect_and_modify` の評価器を **意図的に削除** し、generator パスを発火させる
- ISO27001 でも同様に発火させる
- 比較対象: Phase 6 の qwen 14B 出力 (失敗パターンとして記録済)

## 6. 主指標と合格条件 (実験前固定)

### 6.1 7a (AgentSquare 統合方針)

| ゲート | 条件 |
| --- | --- |
| AgentSquare のレイヤー把握 | Planning / Reasoning / Tool Use / Memory の公開 API が読めている、tsumiki の `goal/` `tools/` `knowledge/skills/` がどこに接続するかが §2.2 表で確定 |
| ライセンス整合 | AgentSquare のライセンスが tsumiki (Apache-2.0 or MIT 想定) と組み合わせ可能 |
| 方針確定 | A 依存利用 or B fork のどちらを採るかが Phase 7a 報告書で明示される |

### 6.2 7b (パッケージ再構成)

| ゲート | 条件 |
| --- | --- |
| ディレクトリ | §3.2 の新規ディレクトリが作成され、`import tsumiki.{input,tools,policy.compose}` がエラーにならない (骨組のみで可) |
| schema 抽象化 | NDA `ng_patterns` と ISO27001 `audit_findings` が `knowledge/schemas/` の共通 schema に乗る (§10.3 の「`schemas/` の抽象化」と整合) |
| リグレッション | NDA Phase 5c の paired diff = +0.261、ISO27001 Phase 6 の +0.029 が再現する (1 seed=42 で誤差 ±0.01 内) |

### 6.3 7c (examples/)

| ゲート | 条件 |
| --- | --- |
| 構造 | `examples/{nda,iso27001}/` に README、goal.yaml、run.sh が揃う |
| **同一フレーム動作** | `examples/nda/run.sh` と `examples/iso27001/run.sh` が **同じ `tsumiki/runner/e2e.py`** を呼び出して end-to-end 完了 (計画書 §10.3 の必須条件) |
| 第三者再現性 | `git clone → uv sync → examples/nda/run.sh` と `examples/iso27001/run.sh` の 2 コマンドで両ドメイン再現可能 (計画書 §10.3 の必須条件) |

### 6.4 7d (LLM プロバイダ + generator 再検証)

| ゲート | 条件 |
| --- | --- |
| プロバイダ 3 系統 | ollama / OpenAI 互換 / Anthropic が `.env` 切替で動く。smoke で各 1 回呼べる |
| generator クラウド再走 | NDA と ISO27001 で意図的削除した評価器が再生成され、`verifier.py` を通過し `store.py` で保存される |
| ガードレール検査 | 生成された評価器が LLM judge を含むなら pairwise / panel_3 / human_calibration のいずれかを必ず持つ |
| **品質判定** | 生成評価器を用いた paired diff が seed 評価器版と ±0.05 内で一致 (NDA, ISO27001 双方) |

### 6.5 7e (AgentSquare 統合)

| ゲート | 条件 |
| --- | --- |
| `policy/compose/` 接続 | tsumiki の TaskSpec + 承認済み評価器を渡して AgentSquare のモジュール探索が起動する |
| 評価器 gate | AgentSquare 起動前に必ず `goal/lookup.py` or `goal/generator.py + verifier.py` を通過している (CLAUDE.md §9 と整合) |
| **両ドメイン動作確証** | `examples/{nda,iso27001}/run.sh` が `policy/compose/` 経由でも完了する |

## 7. 工数見積

| サブ | 内容 | 期間 |
| --- | --- | --- |
| 7a | AgentSquare 調査と統合方針 | 2〜3 日 |
| 7b | パッケージ再構成 + schema 抽象化 | 3〜5 日 |
| 7c | examples/ 整備 + 同一フレーム動作確証 | 2〜3 日 |
| 7d | LLM プロバイダ + generator クラウド再検証 (API 課金あり) | 3〜4 日 |
| 7e | AgentSquare 統合 (compose ラッパ) | 3〜5 日 |
| 合計 | | 13〜20 営業日 |

## 8. 実行手順と再現コマンド (雛形)

### 8.1 7a 着手前の確認

```bash
gh repo view tsinghua-fib-lab/AgentSquare --json licenseInfo,description
```

### 8.2 7b ディレクトリ作成 (例)

```bash
mkdir -p src/tsumiki/{input,tools,policy/compose,policy/optimize,eval/runners,knowledge/extractors,knowledge/schemas}
touch src/tsumiki/{input,tools,policy/compose,policy/optimize,eval/runners,knowledge/extractors,knowledge/schemas}/__init__.py
```

### 8.3 7c examples/ 配置 (例)

```bash
mkdir -p examples/{nda,iso27001}/knowledge
# goal.yaml は手書き、knowledge/ は src/tsumiki/knowledge/skills/<domain>/ から copy or symlink
```

### 8.4 7d generator クラウド試走

```bash
# .env で LLM_PROVIDER=openai_compatible, LLM_BASE_URL=https://api.openai.com/v1,
# LLM_MODEL=gpt-5.4 等を設定

# NDA で評価器を意図的に削除して generator 発火
rm -rf src/tsumiki/eval/generated/nda/detect_and_modify/modification_success_v1
uv run python experiments/test_phase6_generator.py --domain nda --output docs/experiments/phase7d_generator_cloud_nda.jsonl

# ISO27001 で同様
rm -rf src/tsumiki/eval/generated/iso27001/detect_and_modify/audit_findings_success_v1
uv run python experiments/test_phase6_generator.py --domain iso27001 --output docs/experiments/phase7d_generator_cloud_iso27001.jsonl
```

(削除前に seed_*_evaluator.py 系で復元可能であることを確認)

### 8.5 7e AgentSquare 統合 (依存利用版)

```bash
uv add agentsquare    # 上流が PyPI 公開していれば
# or
uv add "agentsquare @ git+https://github.com/tsinghua-fib-lab/AgentSquare@<commit>"
```

`src/tsumiki/policy/compose/` に AgentSquare のモジュール探索を呼び出すラッパを書く。

## 9. リスクと対応

| リスク | 対応 |
| --- | --- |
| AgentSquare の API が `policy/compose/` の必要面を満たさない | 方針 B (fork) に切替。差分は patches/ で管理し上流追随コストを最小化 |
| AgentSquare のライセンスが tsumiki と非互換 | 7a で判明したら設計再検討。tsumiki 側で代替 (`policy/compose/simple_search.py` 等の最小実装) も視野 |
| クラウド GPT-5.4 でも generator 品質不足 | 出力を function calling / structured output 強制 (Phase 7d 試走で再現性を観測) |
| ディレクトリ再編で既存試走が壊れる | 7b の最後で NDA Phase 5c + ISO27001 Phase 6 のリグレッション試走を必須化 |
| クラウド API 課金が想定超 | 7d は事前に「generator 1 回あたりの想定トークン × ドメイン数 × seed 数」を見積、上限を設けて打ち切り |
| `examples/{nda,iso27001}/knowledge/` の二重管理 | symlink 採用、もしくは `tsumiki.knowledge.skills` から動的読込で実体一元化 |
| schema 抽象化で NDA / ISO27001 のニュアンス損失 | 抽象化前後で paired diff が ±0.01 内に収まることを 7b のゲートとして固定 |
| Apache-2.0 NOTICE 遵守漏れ | LICENSE / NOTICE / requirements の整備を 7a で並行 |

## 10. Phase 8 への申し送り

Phase 7 完了時点で OSS リリースに必要な以下が揃う。

- `tsumiki/` パッケージのディレクトリ構造完成
- `examples/{nda,iso27001}/` の 2 件で同一フレーム動作確証
- AgentSquare 統合 (依存または fork 差分管理)
- LLM プロバイダ 3 系統対応
- generator パスのクラウド品質確認

Phase 8 ではこれを土台に README / CONTRIBUTING / LICENSE / Zenn Part 3 / Part 4 を整備する。

## 11. 関連

| 項目 | パス |
| --- | --- |
| 設計 (本書) | `docs/experiments/phase7_design.md` |
| 結果報告 | `docs/experiments/phase7<sub>_<topic>_<date>.md` (実行後に作成) |
| Phase 5c 結果 (NDA 目的駆動 E2E) | [`phase5c_e2e_2026-06-19.md`](phase5c_e2e_2026-06-19.md) |
| Phase 6 結果 (ISO27001 横展開) | [`phase6_e2e_2026-06-19.md`](phase6_e2e_2026-06-19.md) |
| 計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) §10 |
| メモリ | `[[project-tsumiki-status-2026-06-19]]`, `[[project-framework-goal-decisions]]`, `[[project-phase7-next-step]]` |

## 12. Phase 7 完了の定義

以下を満たした時点で Phase 7 完了。

1. 7a 報告書で AgentSquare 統合方針 (A 依存 or B fork) が確定し、根拠が明示されている
2. `src/tsumiki/{input,tools,policy/compose,policy/optimize,eval/runners,knowledge/extractors,knowledge/schemas}` が作成され、`import` がエラーなく通る
3. NDA Phase 5c + ISO27001 Phase 6 の paired diff が再構成後も再現する (誤差 ±0.01)
4. `examples/{nda,iso27001}/` に README / goal.yaml / run.sh が揃い、同一 `runner/e2e.py` で end-to-end 完了する
5. LLM プロバイダが ollama / OpenAI 互換 / Anthropic の 3 系統で smoke 通過
6. generator パスがクラウド GPT-5.4 で NDA + ISO27001 双方で `verifier.py` 通過、保存される
7. AgentSquare 統合 (`policy/compose/`) で `examples/{nda,iso27001}/run.sh` が完了する
8. `phase7<sub>_<topic>_<date>.md` 5 本 (7a〜7e) が記録され、Phase 8 への申し送りが書かれている
