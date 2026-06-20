# Phase 7e 統合結果報告書: AgentSquare partial vendoring と policy/compose 完成

実行期間: 2026-06-19 (1 日に集中)
設計書: [`phase7e_design.md`](phase7e_design.md)
個別結果報告: [7e-1](phase7e1_vendoring_2026-06-19.md) / [7e-2](phase7e2_llm_swap_2026-06-19.md) / [7e-3](phase7e3_search_2026-06-19.md) / [7e-4](phase7e4_compose_2026-06-19.md) / [7e-5](phase7e5_evaluator_gate_2026-06-19.md) / [7e-6](phase7e6_use_compose_2026-06-19.md) / [7-bonus-3](phase7bonus3_cli_overrides_2026-06-19.md)

## 1. 結論先出し

| 項目 | 結果 |
| --- | --- |
| Vendoring (配置 + import) | **完了**. AgentSquare 18 ファイル (3,435 行) を `src/tsumiki/policy/agentsquare/` 配下に取り込み |
| LLM 差し替え | **完了**. `openai` / `langchain` / `utils.llm_response` / `backoff` / `tenacity` 直接呼び出しを全削除し ChatFn / JsonChatFn / BenchmarkFn の 3 種 DI に統一 |
| ライセンス遵守 | **完了**. LICENSE / NOTICE / THIRD_PARTY_LICENSES/AgentSquare/LICENSE + 各 vendored ファイル冒頭の Apache-2.0 derived 表記 |
| 評価器 gate | **完了**. `EvaluatorSpec.is_approved()` + `compose._assert_evaluator_gate_passed` を 3 経路 (lookup / generator / 既存 seed) で動作確認 |
| `compose.run_compose` 動作 | **完了**. `tsumiki.policy.compose` 薄いラッパで `policy.agentsquare.search.run_search` を呼び出し ComposeResult を返す |
| 同一フレーム動作 (実装) | **完了**. `runner/e2e.py` に `use_compose` フラグ + `examples/*/run.sh --use-compose` 起動可能 |
| 同一フレーム動作 (実走 paired_diff 再現) | **ユーザー実走待ち** (NDA +0.261 ±0.05 / ISO27001 +0.029 ±0.05) |
| **テスト** | **290/290 PASS** (Phase 7e 着手前 201 件 → +89 件で 290 件) |
| ruff | **All checks passed** (vendored 範囲は per-file-ignores で E501 のみ許容) |
| CLAUDE.md §3 / §9 整合 | **完了**. LLM プロバイダ層 + 評価器 gate を仕様どおり実装 |

## 2. サブフェーズ別実績

| サブ | 内容 | 工数見積 | 新規ファイル | 新規 test | 報告書 |
| --- | --- | --- | --- | --- | --- |
| 7e-1 | 上流 modules/*.py 4 ファイル取り込み + LICENSE | 0.5 日 | 4 vendored + LICENSE | 0 (7e-2 へ統合) | [7e-1](phase7e1_vendoring_2026-06-19.md) |
| 7e-2 | modules/*.py の LLM 差し替え + langchain 削除 | 1 日 | (上記の書き換え) | 19 | [7e-2](phase7e2_llm_swap_2026-06-19.md) |
| 7e-3 | module_evolution / recombination / predictor / search 取り込み | 1〜1.5 日 | 8 新規 .py + 4 prompts + 4 archives JSON | 31 | [7e-3](phase7e3_search_2026-06-19.md) |
| 7e-4 | `tsumiki.policy.compose` 薄いラッパ実装 | 0.5 日 | 3 (config / runner / __init__) + `make_openai_json_chat_fn` | 12 | [7e-4](phase7e4_compose_2026-06-19.md) |
| 7e-5 | 評価器 gate 整理 (is_approved + 経路 test) | 0.5 日 | `EvaluatorSpec.is_approved()` メソッド | 11 | [7e-5](phase7e5_evaluator_gate_2026-06-19.md) |
| 7-bonus-3 | `LLMSettings.from_env_with_overrides()` CLI 復活 | 0.5 日 | CLI 引数 6 件 | 10 | [7-bonus-3](phase7bonus3_cli_overrides_2026-06-19.md) |
| 7e-6 | examples/{nda,iso27001}/ `--use-compose` 試走対応 | 1 日 + 試走 | `E2EConfig.use_compose` + `_run_compose_auxiliary` | 6 | [7e-6](phase7e6_use_compose_2026-06-19.md) |
| 7e-7 | 本書 (統合結果報告書) | 0.5 日 | - | - | 本書 |

工数見積合計: 5.5〜6 日 → **実績: 1 日に集中**.

### 2.1 新規 test 件数の内訳

| サブ | 新規 test | 累計 |
| --- | --- | --- |
| 7e-2 開始時点 | (既存 201) | 201 |
| 7e-2 | +19 | 220 |
| 7e-3 | +31 | 251 |
| 7e-4 | +12 | 263 |
| 7e-5 | +11 | 274 |
| 7-bonus-3 | +10 | 284 |
| 7e-6 | +6 | **290** |

7e-2 〜 7-bonus-3 + 7e-6 で **+89 件** を新規追加. 既存 201 件は全件 PASS 維持 (リグレッションなし).

## 3. 設計書 §6 ゲート最終充足状況

### 3.1 §6.1 主指標

| 指標 | 状態 | 根拠 |
| --- | --- | --- |
| `import tsumiki.policy.compose.run_compose` が通る | OK | 7e-4 import smoke 13 件 PASS |
| `_assert_evaluator_gate_passed` が未承認時に raise | OK | 7e-4 + 7e-5 で複数経路確認 |
| AgentSquare 探索が起動し `selected_modules` を返す | OK | 7e-3 run_search smoke + 7e-4 run_compose smoke + 7e-6 `_run_compose_auxiliary` smoke |
| `examples/{nda,iso27001}/run.sh --use-compose` の paired_diff が baseline ±0.05 | **ユーザー実走待ち** | 7e-6 で実装完了. 7d-4 と同型でユーザー環境で実走必要 |
| pytest 全体 PASS | OK | 290/290 PASS |

### 3.2 §6.2 合格条件

| ゲート | 条件 | 状態 |
| --- | --- | --- |
| Vendoring 完了 | `agentsquare/{memory,planning,reasoning,tooluse}.py` + `{evolution,recombination,predictor,search}/` が配置され import 通過 | **OK** |
| LLM 差し替え | 取り込んだ全 .py 内で `from openai import OpenAI` が **0 件** | **OK** (ast 検査で確認) |
| ライセンス遵守 | LICENSE / NOTICE / THIRD_PARTY_LICENSES が揃い, 取り込み元コメントが各ファイル冒頭にある | **OK** |
| 評価器 gate | 未承認 EvaluatorSpec で `RuntimeError` (unit test) | **OK** |
| `compose.run_compose` 動作 | mock chat_fn + seed 評価器で `ComposeResult` が返る (unit test) | **OK** |
| 同一フレーム下の挙動 (実装) | `examples/{nda,iso27001}/run.sh --use-compose` が起動可能 | **OK** |
| 同一フレーム下の挙動 (実走 paired_diff 再現) | NDA +0.261 ±0.05 / ISO27001 +0.029 ±0.05 | **ユーザー実走待ち** |
| リグレッション | pytest 全体 PASS, 既存 7d-3 の `LLMSettings` 動作変化なし | **OK** |

## 4. アーキテクチャ最終形 (Phase 7e 完了時点)

```
src/tsumiki/
├── policy/
│   ├── agentsquare/          (Phase 7e-1〜7e-3 で構築. 上流 Apache-2.0 vendoring)
│   │   ├── __init__.py       (8 サブモジュールを公開)
│   │   ├── memory.py         (modules/memory_modules.py を書き換え)
│   │   ├── planning.py       (modules/planning_modules.py)
│   │   ├── reasoning.py      (modules/reasoning_modules.py)
│   │   ├── tooluse.py        (modules/tooluse_modules.py)
│   │   ├── evolution/        (module_evolution + search/module_evolution)
│   │   │   ├── evolve.py
│   │   │   └── prompts/{reasoning,planning,memory,tooluse}.py
│   │   ├── recombination/    (search/recombination.py)
│   │   ├── predictor/        (search/module_predictor.py, alfworld 依存削除)
│   │   └── search/           (search/agent_search.py, alfworld bench 削除)
│   │       ├── loop.py
│   │       └── archives/{memory,planning,reasoning,tooluse}_modules.json
│   ├── compose/              (Phase 7e-4 で構築. 薄いラッパ)
│   │   ├── __init__.py
│   │   ├── config.py         (ComposeConfig / ComposeResult)
│   │   └── runner.py         (run_compose + _assert_evaluator_gate_passed)
│   └── optimize/             (Phase 9+ で DSPy 等を組み込む予定)
│
├── runner/
│   └── e2e.py                (Phase 7e-6 で use_compose フラグ追加)
│
├── goal/
│   └── specs.py              (Phase 7e-5 で is_approved() メソッド追加)
│
├── llm/
│   └── client.py             (Phase 7-bonus-3 で from_env_with_overrides() 追加)
│
└── data/
    └── synthesis.py          (Phase 7e-4 で make_openai_json_chat_fn 追加)
```

外部公開ライセンス:
- `LICENSE` (Apache-2.0, tsumiki 全体)
- `NOTICE` (tsumiki + AgentSquare attribution)
- `THIRD_PARTY_LICENSES/AgentSquare/LICENSE` + `THIRD_PARTY_LICENSES/AgentSquare/README.md` (Phase 7e-1)

## 5. CLAUDE.md ルールとの整合性検証

| ルール | 整合性 |
| --- | --- |
| §3: LLM プロバイダ非依存 (アプリ本体から特定 SDK 直接呼ばない) | **OK**. agentsquare 配下から `openai` SDK 直接呼び出しを全削除. tsumiki.llm 経由のみ |
| §4: 再現性 (temperature=0, seed 固定) | **OK**. `LLMSettings.temperature` を `.env` / CLI 経由で設定. `make_openai_*_chat_fn` で seed 強制 |
| §5: コード規約 (ruff / 型注釈 / 絵文字禁止) | **OK**. All checks passed. 型注釈完備 |
| §6: ディレクトリ構成 | **OK**. `src/tsumiki/policy/` 配下に AgentSquare 統合 |
| §7: データ・シークレット (data/ をコミットしない, .env コミットしない) | **OK**. archives/*.json は alfworld の公開モジュール記述で機密性なし |
| §9: 評価器が無い状態で自動探索を回さない | **OK**. `_assert_evaluator_gate_passed` で強制. 3 経路で動作確認 |
| §9: 汎用エージェント自動生成フレームワークをゼロから自作しない (fork 推奨) | **OK**. AgentSquare の partial vendoring を採用 |
| §9: アプリ本体から特定 LLM プロバイダ SDK を直接呼ばない | **OK**. agentsquare 配下も含めて全て `tsumiki.llm` 経由 |
| §11: 結論先出し / table 形式 / 一貫性 | **OK**. 各報告書で実施 |

## 6. ユーザー実走コマンド (paired_diff 再現確認)

### 6.1 Azure OpenAI 経由

```bash
# .env を 7d-4 と同じ Azure OpenAI 設定にしておく
bash examples/nda/run.sh --use-compose --compose-max-depth 1
bash examples/iso27001/run.sh --use-compose --compose-max-depth 1
```

期待:
- NDA: `paired_diff` が +0.261 ±0.05 / gate=OK / `compose selected` が表示
- ISO27001: `paired_diff` が +0.029 ±0.05 / gate=OK / `compose selected` が表示

### 6.2 ollama 経由 (低コスト smoke)

```bash
bash examples/nda/run.sh \
  --use-compose --compose-max-depth 1 \
  --llm-provider openai_compatible \
  --llm-base-url http://localhost:11434/v1 \
  --llm-model hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M
```

Phase 7-bonus-3 の `--llm-*` 引数で Azure ↔ ollama を CLI 切り替え可能.

### 6.3 試走結果の記録方針

実走完了後, 本書 §6.4 (新設) に結果を追記する (paired_diff / gate / compose selected_modules / search_score).

### 6.4 試走結果 (ユーザー実走後に追記)

```
未実施.
```

## 7. Phase 7e で実装しなかったこと (Phase 9+ 持ち越し)

| 項目 | 理由 |
| --- | --- |
| 本物の `benchmark_fn` (Agent dict → 合成 chat_fn → variant 実行 → score) | `agentsquare.{planning,reasoning,memory,tooluse}` 4 モジュールを Agent dict の "name" 文字列から実モジュールクラスに引いて連鎖させる大規模実装が必要. 7e は「薄いラッパ」段階. Phase 9+ で. |
| archives の domain 適応 | 現状 `agentsquare/search/archives/*.json` は alfworld 由来. NDA / ISO27001 向け初期 archive を `archives/{nda,iso27001}/` 配下に新規作成するのは Phase 9+. |
| prompts の domain 適応 | `agentsquare/evolution/prompts/*.py` の alfworld 固有テキストはそのまま温存. compose 経由の task_description 注入で代替. 本物の domain 適応は Phase 9+. |
| `evolve()` 出力 code の `chat_fn` 化 | 上流 LLM が生成する evolution code に含まれる `llm_response(...)` を `chat_fn(...)` に書き換える後処理は Phase 9+. |
| Phase 7-bonus-1 (generator 主 metric 整合) | 7d-4 で発覚した generator 下流契約問題. Phase 9+ で対応. |
| Phase 7-bonus-2 (input_signature schemas 固定) | 同上. |
| AgentSquare 探索の hyperparameter 最適化 | 設計書 §6.3 で除外. Phase 9+. |
| 3 seed CI / 人手較正 | 同上. Phase 9+. |

## 8. Phase 8 への申し送り (Zenn Part 3/4 + OSS リリース)

### 8.1 公開準備チェックリスト

| 項目 | 状態 | 補足 |
| --- | --- | --- |
| Apache-2.0 LICENSE | OK | tsumiki ルート |
| NOTICE | OK | tsumiki + AgentSquare attribution |
| THIRD_PARTY_LICENSES/AgentSquare/ | OK | LICENSE 全文 + README |
| pyproject.toml license フィールド | OK | `license = "Apache-2.0"`, `license-files = ["LICENSE", "NOTICE"]` |
| README | **未着手** | Phase 8 で書く. tsumiki の概要 + 検証結果サマリ + クイックスタート |
| CONTRIBUTING.md | **未着手** | Phase 8 で書く. PR 規約, テスト方針, ライセンス |
| examples/ | OK | NDA + ISO27001 の 2 件. README 充実は Phase 8 で |
| 結果報告書 | OK | Phase 5a 〜 7e-7 (全て docs/experiments/ 配下) |

### 8.2 Zenn 連載構成 (案)

| パート | 内容 | 元資料 |
| --- | --- | --- |
| Part 1 (既出) | 仮説と検証計画 | `agent_reuse_verification_plan.md` |
| Part 2 (既出) | Phase 1〜4 ベースライン構築と再利用検証 | Phase 1〜6 結果報告書 |
| **Part 3 (Phase 8 で執筆)** | 目的駆動への進化 (Phase 5c / 6) と AgentSquare 統合 (Phase 7) | Phase 5c / 6 / 7a〜7e 結果報告書 |
| **Part 4 (Phase 8 で執筆)** | OSS としての設計と再現性 (CLAUDE.md ルール, ディレクトリ構成, テスト戦略) | CLAUDE.md, pyproject.toml, tests/ |

### 8.3 OSS リリース時の警告

- README に「Phase 7e の compose 統合は **薄いラッパ段階**」を明記. benchmark_fn の本物実装は Phase 9+ である旨を断る
- archives は alfworld 由来であり, NDA / ISO27001 用 domain archive は Phase 9+ である旨を明記
- ユーザー実走確認待ちのため, README の paired_diff 数値は Phase 5c / 6 baseline を引用し, `--use-compose` 経由の数値は Phase 9+ 確認後に追記
- Phase 7-bonus-1 (generator 主 metric 整合) / 7-bonus-2 (input_signature 固定) は β 機能として generator パスを「実験的」扱いと明示

## 9. まとめ

Phase 7e は AgentSquare partial vendoring と `tsumiki.policy.compose` 薄いラッパの完成を達成. 設計書 §6.2 の合格条件のうち, **実装ゲート 7/8 が完了**. 残る 1 件 (実走 paired_diff 再現) はユーザー環境での実走待ち (Phase 7d-4 と同型の運用).

工数見積 5.5〜6 日に対し **実績は 1 日に集中**. プロセス効率の要因:
- Phase 7a で方針 B-2 (partial vendoring) を事前確定したため取り込み範囲で迷わなかった
- 7e-1 〜 7e-3 で vendoring + 差し替え, 7e-4 〜 7e-6 で wiring と 2 段階に分けた構造が功を奏した
- 各サブで結果報告書を都度書き, 申し送りを次サブが拾う構造で手戻りゼロ

CLAUDE.md ルール全件遵守. 290/290 test PASS でリグレッションなし.

次フェーズ: **Phase 8 (Zenn Part 3/4 公開 + OSS リリース, 2 週見積)**. 並行で Phase 7-bonus-1 / 7-bonus-2 を任意整理として実施可能.

## 10. 関連

| 項目 | パス |
| --- | --- |
| Phase 7 全体設計 | [`phase7_design.md`](phase7_design.md) |
| Phase 7e 設計 | [`phase7e_design.md`](phase7e_design.md) |
| Phase 7a 結果 | [`phase7a_agentsquare_2026-06-19.md`](phase7a_agentsquare_2026-06-19.md) |
| Phase 7b 結果 | [`phase7b_packaging_2026-06-19.md`](phase7b_packaging_2026-06-19.md) |
| Phase 7c 結果 | [`phase7c_examples_2026-06-19.md`](phase7c_examples_2026-06-19.md) |
| Phase 7d 結果 | [`phase7d_provider_and_generator_2026-06-19.md`](phase7d_provider_and_generator_2026-06-19.md) |
| Phase 7e-1 結果 | [`phase7e1_vendoring_2026-06-19.md`](phase7e1_vendoring_2026-06-19.md) |
| Phase 7e-2 結果 | [`phase7e2_llm_swap_2026-06-19.md`](phase7e2_llm_swap_2026-06-19.md) |
| Phase 7e-3 結果 | [`phase7e3_search_2026-06-19.md`](phase7e3_search_2026-06-19.md) |
| Phase 7e-4 結果 | [`phase7e4_compose_2026-06-19.md`](phase7e4_compose_2026-06-19.md) |
| Phase 7e-5 結果 | [`phase7e5_evaluator_gate_2026-06-19.md`](phase7e5_evaluator_gate_2026-06-19.md) |
| Phase 7e-6 結果 | [`phase7e6_use_compose_2026-06-19.md`](phase7e6_use_compose_2026-06-19.md) |
| Phase 7-bonus-3 結果 | [`phase7bonus3_cli_overrides_2026-06-19.md`](phase7bonus3_cli_overrides_2026-06-19.md) |
| 計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) |
| Vendoring 記録 | [`../agentsquare_vendoring.md`](../agentsquare_vendoring.md) |
| 上流リポジトリ | https://github.com/tsinghua-fib-lab/AgentSquare (SHA: `8f5b3fe5d8a32f9b59d20370823bef2a2c86928c`) |
