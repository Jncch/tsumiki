# AgentSquare vendoring 記録

Phase 7a §5 で確定した方針 B-2 (partial vendoring) に基づく取り込み記録.
配置先: `src/tsumiki/policy/agentsquare/`
ライセンス: Apache-2.0 (`THIRD_PARTY_LICENSES/AgentSquare/LICENSE`, `NOTICE`).

## 1. 上流情報

| 項目 | 値 |
| --- | --- |
| リポジトリ | https://github.com/tsinghua-fib-lab/AgentSquare |
| 取り込み commit SHA | `8f5b3fe5d8a32f9b59d20370823bef2a2c86928c` |
| 上流ブランチ | `main` |
| 取り込み日 | 2026-06-19 (Phase 7e-1) |
| ライセンス宣言 | README に "Code License: Apache-2.0" (リポジトリトップに LICENSE ファイル不在のため Apache 公式から全文を別途配置) |

## 2. 取り込み範囲 (Phase 7a §5.1 の B-2 と一致)

### 2.1 Phase 7e-1 で取り込み済 (4 ファイル)

| 上流パス | 配置先 | サイズ |
| --- | --- | --- |
| `modules/memory_modules.py` | `src/tsumiki/policy/agentsquare/memory.py` | 11270 bytes |
| `modules/planning_modules.py` | `src/tsumiki/policy/agentsquare/planning.py` | 8861 bytes |
| `modules/reasoning_modules.py` | `src/tsumiki/policy/agentsquare/reasoning.py` | 15623 bytes |
| `modules/tooluse_modules.py` | `src/tsumiki/policy/agentsquare/tooluse.py` | 11873 bytes |

### 2.2 Phase 7e-3 (2026-06-19) で取り込み済

| 上流パス | 配置先 | 行数 (参考) |
| --- | --- | --- |
| `module_evolution/prompt_{reasoning,planning,memory,tooluse}.py` | `src/tsumiki/policy/agentsquare/evolution/prompts/*.py` | 4 ファイル, 計 約 1,577 行 (上流のまま温存) |
| `search/module_evolution.py` (主体) + `module_evolution/module_evolution.py` (参考) | `src/tsumiki/policy/agentsquare/evolution/evolve.py` | 198 行 (新規) |
| `search/recombination.py` | `src/tsumiki/policy/agentsquare/recombination/recombine.py` | 125 行 (新規) |
| `search/module_predictor.py` | `src/tsumiki/policy/agentsquare/predictor/predictor.py` | 178 行 (新規) |
| `search/agent_search.py` | `src/tsumiki/policy/agentsquare/search/loop.py` | 220 行 (新規, alfworld 固有部 削除済) |
| `search/{memory,planning,reasoning,tooluse}_modules.json` | `src/tsumiki/policy/agentsquare/search/archives/*.json` | 4 ファイル (上流のまま) |

採用しなかった上流ファイル:
- `module_recombination/module_recombination.py` (トップレベル副作用付き): より整理された `search/recombination.py` を採用.
- `module_evolution/module_evolution.py` (CLI 版): `search/module_evolution.py` の関数化版を採用. 参考実装として記録のみ.

### 2.3 取り込まないもの (Phase 7a §5.2 の捨てるリストと一致)

- `tasks/{alfworld,webshop,m3tooleval,sciworld}/` 全捨て (ベンチマーク統合、tsumiki と無関係)
- 上流 `requirements.txt` の `alfworld` 0.3.5, `langchain` 0.3.3, `langchain_chroma` 0.1.4, `langchain_openai` 0.2.2 (CLAUDE.md §3 と整合)
- 上流の補助ファイル (`tasks/*/utils.py`, `tasks/alfworld/planning_prompt.py`, `tasks/m3tooleval/tooluse_IO_pool.py`) は取り込まず, tsumiki 側で代替実装する (Phase 7e-2)
- video.mp4 等のバイナリ (git-lfs 必須, ライセンス NOTICE のみ参照)

## 3. 改変サマリ

### 3.1 Phase 7e-1 で実施

各 vendored ファイルの先頭に **vendoring ヘッダ docstring** を追加. 内容:

- 上流 URL + commit SHA
- 取り込み日 (Phase 7e-1)
- WARNING: 現状 import 不可の理由 (タスク固有 utils / langchain 依存)
- 7e-2 で実施する書き換え予定

ファイル中身 (クラス定義・ロジック) は上流のまま無改変.

### 3.2 Phase 7e-2 で実施予定

1. **LLM 呼び出しの差し替え** (CLAUDE.md §3 と整合)
   - 上流 `from utils import llm_response` (タスク固有) を削除
   - tsumiki 側の `chat_fn` (DI) を各クラスのコンストラクタで受け取る形に書き換え
2. **langchain 依存の削除**
   - `MemoryBase.__init__` の `OpenAIEmbeddings()` / `Chroma(...)` を削除
   - `ToolUseToolBench` / `ToolUseToolBenchFormer` (langchain ベースの embedding 検索) は variant ごと削除を検討
   - `MemoryDILU`, `MemoryGenerative` 等の variant は tsumiki の `knowledge/skills/` 参照に置換
3. **`gpt-3.5-turbo` 等のモデル名ハードコード削除** (settings.model 経由に統一)
4. **タスク固有プロンプト/ツール pool 依存の削除**
   - `from planning_prompt import *` (tasks/alfworld 固有) を tsumiki 側のドメイン非依存プロンプトに置換
   - `from tooluse_IO_pool import tooluse_IO_pool` (tasks/m3tooleval 固有) を `tsumiki.tools` プラグイン経由のツール pool に置換

### 3.3 Phase 7e-3 (2026-06-19) で実施済

- `evolve.py`: `from openai import OpenAI` 削除, `backoff` 削除, `JsonChatFn` (DI) 化, `output_dir` 引数化, `__main__` 削除.
- `recombine.py`: `from utils import llm_response` 削除, `ChatFn` (DI) 化, `eval()` → `ast.literal_eval()`.
- `predictor.py`: `from modules_predictor.*` wildcard 削除, `from openai import OpenAI` / 自前 `llm_response` 削除, `inspect.getsource` → archives lookup, `alfworld_results.json` 読み込み削除 (golden_cases 引数化), `eval()` → `json.loads()`.
- `loop.py`: alfworld 固有 (`run_benchmark`, `write_test_module`, `test_*`, `ProcessPoolExecutor`) 削除, `benchmark_fn: BenchmarkFn` DI 化, `task_description` 引数化.
- prompts (4 ファイル): 本体は上流のまま温存. `get_prompt_X(archive, last_feedback=None)` シグネチャ拡張のみ (search 側呼び出し互換).
- 上流の `eval()` 直接呼び出しを全て `ast.literal_eval` / `json.loads` に置換 (任意コード実行回避).

## 4. ruff / pytest 設定 (確定)

Phase 7e-2 で全体 lint exclude は解除済. 7e-3 で以下のみ残る:

```toml
[tool.ruff.lint.per-file-ignores]
"src/tsumiki/policy/agentsquare/*.py" = ["E501"]
"src/tsumiki/policy/agentsquare/**/*.py" = ["E501"]

[tool.pytest.ini_options]
filterwarnings = [
    # vendored prompts の alfworld archive code 文字列内の invalid escape sequence
    # (\s, \{ 等) を抑制. ファイル内容は文字列リテラルで実行されない.
    "ignore:invalid escape sequence:SyntaxWarning",
]
```

vendored 範囲全体が通常の ruff / pyright チェックに乗る状態. E501 のみ alfworld プロンプト本文の温存のため許容.

## 5. 上流追随ポリシー (Phase 7a §5.4)

- 上流更新の確認は **四半期に 1 回** (2026 Q3 から)
- 取り込み範囲が modules/ + search/ 系に限定されており追随コスト低
- セキュリティ修正があれば即時取り込み (取り込み範囲内のみ)
- 上流 commit SHA は本書 §1 の表で履歴管理

### 5.1 更新時の手順 (将来)

1. `git ls-remote https://github.com/tsinghua-fib-lab/AgentSquare HEAD` で最新 SHA 取得
2. `git diff` で取り込み範囲の差分を確認
3. 差分が tsumiki の改変と整合する場合のみ取り込み
4. 本書 §1 の取り込み commit SHA を更新

## 6. ライセンス NOTICE

各 vendored ファイル冒頭の docstring に以下を明記:

- 「Apache-2.0」
- 「Upstream: https://github.com/tsinghua-fib-lab/AgentSquare/blob/<SHA>/...」
- 「Vendored at Phase 7e-1 (2026-06-19)」

リポジトリルートの `NOTICE` でも上流 attribution を提示.

## 7. 関連

- 上流調査: [`experiments/phase7a_agentsquare_2026-06-19.md`](experiments/phase7a_agentsquare_2026-06-19.md)
- 7e 全体設計: [`experiments/phase7e_design.md`](experiments/phase7e_design.md)
- LICENSE (Apache-2.0 全文): [`../THIRD_PARTY_LICENSES/AgentSquare/LICENSE`](../THIRD_PARTY_LICENSES/AgentSquare/LICENSE)
- NOTICE: [`../NOTICE`](../NOTICE)
- 計画書: [`agent_reuse_verification_plan.md`](agent_reuse_verification_plan.md) §10
