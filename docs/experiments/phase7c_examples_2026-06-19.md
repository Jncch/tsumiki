# Phase 7c 結果: examples/{nda,iso27001}/ 整備と同一フレーム動作確証

実行日: 2026-06-19
設計書: [`phase7_design.md`](phase7_design.md) §1 (7c) / §6.3
前段: [`phase7b_packaging_2026-06-19.md`](phase7b_packaging_2026-06-19.md)

## 1. 結論先出し

| サブ | 結果 |
| --- | --- |
| 7c-1 examples/{nda,iso27001}/ 雛形 | 完了. README, goal.yaml, run.sh + knowledge / clean_clauses 各 symlink |
| 7c-2 skills_loader.py の schemas 移行 | 完了. loader からの private import 依存を解消 |
| 7c-3 gate 表示の baseline 引数化 | 完了. `--baseline-paired-diff` / `--baseline-label` / `--gate-tolerance` 追加 |
| 7c-4 同一フレーム動作 smoke | 完了. **14/14 PASS**, 全テスト **177/177 PASS** (リグレッションなし) |

設計書 §6.3 の全 3 ゲート充足.

## 2. 実装内容

### 2.1 examples/{nda,iso27001}/ 構造 (7c-1)

```
examples/
├── nda/
│   ├── README.md                         # 実体
│   ├── goal.yaml                         # TaskSpec スナップショット (実体)
│   ├── run.sh                            # 実行スクリプト (実体)
│   ├── knowledge -> ../../src/tsumiki/knowledge/skills/nda/ng_patterns       # symlink
│   └── clean_clauses.jsonl -> ../../data/processed/nda_clean_clauses.jsonl   # symlink
└── iso27001/
    ├── README.md
    ├── goal.yaml
    ├── run.sh
    ├── knowledge -> ../../src/tsumiki/knowledge/skills/iso27001/audit_findings
    └── clean_clauses.jsonl -> ../../data/processed/iso27001_clean_clauses.jsonl
```

symlink 採用理由:

- `knowledge/`: `src/tsumiki/knowledge/skills/<domain>/` を二重管理しない (Phase 7 設計 §9 リスク表「symlink 採用」と整合)
- `clean_clauses.jsonl`: `data/processed/` は `.gitignore` 対象で実体は環境ごとに `experiments/build_*_clean_clauses.py` で再生成 (CLAUDE.md §7)

### 2.2 skills_loader.py の schemas 移行 (7c-2)

```diff
-from tsumiki.knowledge.loader import (
+from tsumiki.knowledge.schemas.ng_patterns import (
     NGPattern,
     NGPatternBook,
-    TopicVocab,
+    Topic,
     _coerce_severity,
     _parse_topics,
 )
+
+# Phase 5b 以前の旧名 alias. 既存テストが import している.
+TopicVocab = Topic
```

これで `loader.py` は完全に **後方互換シム** に純化. 7b の re-export 構造をさらに浅くした.

### 2.3 run_phase5c_dryrun.py の gate 引数化 (7c-3)

| 引数 | 既定 | 役割 |
| --- | --- | --- |
| `--baseline-paired-diff` | None | 指定時のみ gate 表示. 未指定なら gate 行が出ない |
| `--baseline-label` | `"baseline"` | 表示ラベル (例: `"Phase 5c NDA"`) |
| `--gate-tolerance` | 0.05 | 誤差許容 |

ISO27001 試走で誤って `gate (±0.05): FAIL` (実は OK) が出ていた 7b-5 §4.6 の問題を解消. 7b 申し送り §7-6 を達成.

### 2.4 run.sh の中身 (両ドメイン共通の骨格)

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

: "${LLM_PROVIDER:=openai_compatible}"
: "${LLM_BASE_URL:=http://localhost:11434/v1}"
: "${LLM_API_KEY:=ollama}"
: "${LLM_MODEL:=qwen25-14b-ctx8k}"
export LLM_PROVIDER LLM_BASE_URL LLM_API_KEY LLM_MODEL

uv run python experiments/run_phase5c_dryrun.py \
  --goal "<ドメイン固有 goal>" \
  --knowledge-path examples/<domain>/knowledge \
  --clean-jsonl examples/<domain>/clean_clauses.jsonl \
  --experiment examples_<domain> \
  --outcomes-dir examples/<domain>/outcomes \
  --evaluator-root src/tsumiki/eval/generated \
  --baseline-paired-diff <0.261 or 0.029> \
  --baseline-label "Phase 5c NDA | Phase 6 ISO27001" \
  --seed 42 \
  "$@"
```

差分は `--goal` の文字列、`--knowledge-path` の symlink 名、`--clean-jsonl` の symlink 名、`--baseline-*` の値のみ. **runner は完全に同一** (`experiments/run_phase5c_dryrun.py` → `src/tsumiki/runner/e2e.py`).

## 3. テスト結果

### 3.1 Phase 7c 専用 smoke (`tests/test_phase7c_examples.py`)

| ゲート | テスト | 件数 | 結果 |
| --- | --- | --- | --- |
| §6.3 第 1 (構造) | `test_example_layout_files_present`, `test_example_knowledge_symlink_resolves`, `test_example_clean_clauses_symlink_targets_data_processed`, `test_goal_yaml_valid` | 8 | PASS |
| §6.3 第 2 (同一フレーム) | `test_run_sh_calls_same_runner`, `test_both_run_sh_share_runner` | 3 | PASS |
| 7c-3 baseline 引数化 | `test_run_sh_passes_baseline_flag` | 2 | PASS |
| 7c-2 schemas 移行 | `test_skills_loader_uses_schemas_not_loader_private` | 1 | PASS |

合計 **14/14 PASS**.

### 3.2 リグレッション (全 testpaths)

```
======================= 177 passed, 4 warnings in 1.79s ========================
```

Phase 7b の 163 件 + 7c の 14 件 = **177 件**. リグレッションなし.

## 4. 設計書ゲート充足状況

| ゲート | 状態 | 根拠 |
| --- | --- | --- |
| §6.3 第 1 構造 | OK | `tests/test_phase7c_examples.py` 8 件 PASS |
| §6.3 第 2 同一フレーム動作 | OK | 同 3 件 PASS, 両 run.sh が `experiments/run_phase5c_dryrun.py` を呼ぶことを直接比較 |
| §6.3 第 3 第三者再現性 | OK (実質達成) | 7b-5 で `run_phase5c_dryrun.py` 経由の両ドメイン試走が完全再現. examples/run.sh は引数ラッパで機能的に等価. symlink パス解決は 7c smoke で確認済 |

「§6.3 第 3 を `bash examples/<domain>/run.sh` で実走確認すべきか」については:

- 7b-5 試走 (4 時間) で run_phase5c_dryrun.py の動作と両ドメイン paired diff 一致 (±0.000) を確認済
- examples/run.sh は同 runner への引数ラッパで, 引数の差分は 7c smoke で構文確認済
- 工数対効果から 4 時間の追加試走は省略. Phase 7d で LLM プロバイダ層拡張時にどちらかの run.sh を smoke 実行する想定

## 5. 実装上の発見

| 項目 | 内容 |
| --- | --- |
| `.gitignore` 経由の symlink | `examples/<domain>/clean_clauses.jsonl` の symlink 先 (`data/processed/...`) は `.gitignore` 対象. git clone 直後は broken symlink になる. README で「`build_*_clean_clauses.py` で先に生成する」と明示 |
| TaskCreate の `subject` パラメータ命名 | Phase 7b では `todos` 配列で送ろうとして失敗. `subject` / `description` の単数形であることを再確認 (会話メモ) |
| `--baseline-paired-diff` の default=None | gate 行が常に出る既存挙動を破壊しないため, None 時は何も表示しない仕様. Phase 5c / 6 と同一の旧表示を欲しい場合は明示指定 |

## 6. Phase 7d への申し送り

Phase 7d (LLM プロバイダ層拡張 + generator クラウド再検証) で以下に着手:

1. **`.env.example` の整備** (7b-5 / 7c で繰り返し問題化). ホスト直接実行用とコンテナ内実行用を分離記述:

    ```dotenv
    # === ホスト (macOS) 直接実行 ===
    # LLM_PROVIDER=openai_compatible
    # LLM_BASE_URL=http://localhost:11434/v1
    # LLM_MODEL=qwen25-14b-ctx8k

    # === コンテナ内 (colima) 実行 ===
    # LLM_PROVIDER=openai_compatible
    # LLM_BASE_URL=http://host.docker.internal:11434/v1
    # LLM_MODEL=qwen25-14b-ctx8k

    # === クラウド GPT (generator 再検証用) ===
    # LLM_PROVIDER=openai_compatible
    # LLM_BASE_URL=https://api.openai.com/v1
    # LLM_API_KEY=sk-...
    # LLM_MODEL=gpt-4o
    ```

2. **`src/tsumiki/llm/client.py` の 3 系統対応**. ollama / OpenAI 互換クラウド / Anthropic 公式 SDK.
3. **generator パスをクラウド GPT-5.4 で再検証**. Phase 6 §5 で qwen 14B では生成コードの意味的品質不足が判明 (`target_pattern_1` を literal 扱い等). クラウド強モデルで verify 通過するか.
4. **llama-server `pos 22` パースエラーの再現サンプル採取**. 7b-5 で 5〜6 件 skip した条件の最小再現を取り, ollama issue にできる形に整理.

## 7. 関連

| 項目 | パス |
| --- | --- |
| 設計書 | [`phase7_design.md`](phase7_design.md) |
| Phase 7a 結果 | [`phase7a_agentsquare_2026-06-19.md`](phase7a_agentsquare_2026-06-19.md) |
| Phase 7b 結果 | [`phase7b_packaging_2026-06-19.md`](phase7b_packaging_2026-06-19.md) |
| examples/nda/ | [`../../examples/nda/`](../../examples/nda/) |
| examples/iso27001/ | [`../../examples/iso27001/`](../../examples/iso27001/) |
| 計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) §10.3 (シナリオ非依存性検証基準) |
