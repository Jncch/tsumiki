# Phase 7e-3 結果: AgentSquare module_evolution / recombination / predictor / search 取り込み + LLM 差し替え

実行日: 2026-06-19
設計書: [`phase7e_design.md`](phase7e_design.md) §2.1 / §2.2 / §3 / §6
前段: [`phase7e2_llm_swap_2026-06-19.md`](phase7e2_llm_swap_2026-06-19.md)

## 1. 結論先出し

| 項目 | 結果 |
| --- | --- |
| evolution 取り込み | 完了. `module_evolution/` + `search/module_evolution.py` を統合し ChatFn DI 化 |
| recombination 取り込み | 完了. `search/recombination.py` を関数化版で採用. `eval()` を `ast.literal_eval()` に置換 |
| predictor 取り込み | 完了. `search/module_predictor.py` を採用. alfworld 固有 wildcard import 削除, golden_cases 引数化 |
| search 取り込み | 完了. `search/agent_search.py` の alfworld 固有ベンチマーク (`run_benchmark` 系) を削除し `benchmark_fn: BenchmarkFn` を DI 化 |
| **LLM 差し替え** | **完了** (`from openai`, `from utils`, `import openai`, `import backoff`, `import tenacity` 全削除) |
| **import 通過** | **OK**. 13 モジュール全て import smoke 通過 |
| **テスト** | **251/251 PASS** (Phase 7e-3 新規 31 件 + 既存 220 件) |
| ruff (agentsquare + tests) | All checks passed (E501 のみ per-file ignore で許容) |
| pyproject filterwarnings | vendored prompts の SyntaxWarning (alfworld archive code 文字列内の `\s`, `\{`) を抑制 |

## 2. 実装内容

### 2.1 配置 (上流ファイル → tsumiki)

| 上流パス | 配置先 (tsumiki) | 行数 | 改変 |
| --- | --- | --- | --- |
| `module_evolution/prompt_reasoning.py` | `evolution/prompts/reasoning.py` | 524 | vendoring header + `get_prompt_reasoning(archive, last_feedback=None)` シグネチャ拡張 |
| `module_evolution/prompt_planning.py` | `evolution/prompts/planning.py` | 405 | 同上 (memory/tooluse も同型) |
| `module_evolution/prompt_memory.py` | `evolution/prompts/memory.py` | 362 | 同上 |
| `module_evolution/prompt_tooluse.py` | `evolution/prompts/tooluse.py` | 286 | 同上 |
| `search/module_evolution.py` (主体) + `module_evolution/module_evolution.py` (参考) | `evolution/evolve.py` (新規) | 198 | ChatFn DI + `backoff` 削除 + `output_dir` 引数化 + `__main__` 削除 |
| `search/recombination.py` | `recombination/recombine.py` | 125 | ChatFn DI + `eval()` → `ast.literal_eval()` + model ハードコード削除 |
| `search/module_predictor.py` | `predictor/predictor.py` | 178 | ChatFn DI + `modules_predictor.*` wildcard 削除 + golden_cases 引数化 + `inspect.getsource` → archives lookup |
| `search/agent_search.py` | `search/loop.py` | 220 | alfworld 固有 (`run_benchmark`, `write_test_module`, `test_*`, `ProcessPoolExecutor`) **削除** + `benchmark_fn: BenchmarkFn` DI 化 |
| `search/{memory,planning,reasoning,tooluse}_modules.json` | `search/archives/*.json` | 4 ファイル | 上流のまま (alfworld archive を初期 archive として保持) |

`module_recombination/module_recombination.py` (トップレベル副作用付き) は採用せず, より整理された `search/recombination.py` 版を採用.

### 2.2 ファイル別変更詳細

#### evolution/evolve.py (新規)

```python
JsonChatFn = Callable[[list[dict[str, str]]], dict[str, Any]]

def evolve(
    current_agent: dict[str, str],
    planning_archive, reasoning_archive, tooluse_archive, memory_archive,
    json_chat_fn: JsonChatFn,
    output_dir: Path | None = None,
) -> tuple[list[dict[str, str]], dict, dict, dict, dict]:
    ...
```

- 上流の `backoff.on_exception` を削除. リトライは `tsumiki.llm` 層で吸収する想定.
- 上流の `while not ensure_keys_exist(...): ...` 無限ループに `max_retries=5` の上限を追加.
- 上流の `with open('output_*.jsonl', 'a')` を `output_dir / 'output_X.jsonl'` 形式に変更し,
  `output_dir=None` で書き出しスキップ.
- `_filter_archive`, `_fix_code_escapes`, `_solve_with_keys` をヘルパ関数として分離.

#### evolution/prompts/*.py (vendored)

- 各ファイル冒頭に vendoring docstring 追加.
- `get_prompt_X(current_archive)` を `get_prompt_X(current_archive, last_feedback=None)` に拡張
  (`search/module_evolution.py` 呼び出し側との互換).
- `last_feedback` は本実装では未使用 (上流 prompts 自体が feedback 非対応の構造).
- 本体の alfworld 固有プロンプト (archive エントリの長大な英語 + sample code 文字列) は **上流のまま温存**.
- archive code 文字列内に `from langchain ...`, `from utils import llm_response` 等が含まれるが
  これらは Python 文字列リテラル (実行されない). ast ベースの import 検査で除外確認.

#### recombination/recombine.py (新規)

- 上流 `from utils import llm_response` → `chat_fn: ChatFn` DI に置換.
- `eval(response)` → `ast.literal_eval(response)` (任意コード実行回避).
- `model = 'gpt-4o-mini'` ハードコード削除.
- `_parse_agent_dict` ヘルパ追加: `literal_eval` 失敗時は最初の `{...}` ブロックを抽出して再試行.
  失敗時は `{}` を返し, 呼び出し側が `current_agent` の値で fallback する.

#### predictor/predictor.py (新規)

- 上流の `from modules_predictor.{planning,reasoning,tooluse,memory}_modules import *` を **削除**.
  alfworld benchmark 統合に依存する wildcard import を排除.
- `inspect.getsource(class_name)` 経路を廃止し, `archives[module_type]` の `code` フィールドを
  直接利用する `_build_agent_code` ヘルパに置換.
- 上流の `with open('alfworld_results.json', 'r')` を削除. golden_cases を関数引数化.
- `eval(response)` → `json.loads(response)` (chat_fn 側で JSON mode 強制).
- 上流の `random.seed(42)` をローカル `random.Random(seed)` に変更 (グローバル状態回避).
- 上流 `from openai import OpenAI` / 自前 `llm_response`, `get_completion`, `get_chat` を **削除**.

#### search/loop.py (新規)

- 上流 `agent_search.py` (534 行) の **大幅改変**:
  - alfworld 固有 (`run_benchmark`, `write_test_module`, `remove_test_module`, `prepare_test_agent`,
    `cleanup_test_modules`, `test_new_modules`, `test_agent`) を **削除**.
  - `concurrent.futures.ProcessPoolExecutor` を **削除** (alfworld 並列依存).
  - `agent_search()` を `run_search(benchmark_fn, chat_fn, json_chat_fn, task_description, ...)` に
    関数化. `benchmark_fn: Callable[[Agent], float]` を DI で受け取り, ドメイン非依存に.
  - 上流の `TASK_DESCRIPTION = "ALFworld is ..."` ハードコードを `task_description` 引数化.
  - `save_to_json` のロギングを `output_dir: Path | None` 引数化.
- `load_modules_from_json` / `load_default_archives` を提供. 同梱 archives/*.json (4 種) を使う.
- evolution で生成された新モジュールを `candidates` / `archives` に追加してから `benchmark_fn` に渡す
  形に簡略化 (上流の `write_test_module` ファイル書き出し経路を廃止).

#### `agentsquare/__init__.py` 更新

```python
from tsumiki.policy.agentsquare import (
    evolution, memory, planning, predictor, reasoning,
    recombination, search, tooluse,
)
__all__ = ["evolution", "memory", "planning", "predictor",
           "reasoning", "recombination", "search", "tooluse"]
```

### 2.3 `pyproject.toml` 更新

- `[tool.ruff.lint.per-file-ignores]` を inline 辞書形式から section 形式に変更し,
  `src/tsumiki/policy/agentsquare/**/*.py` (再帰 glob) も E501 許容対象に追加.
- `[tool.pytest.ini_options].filterwarnings` を追加し, vendored prompts の
  `SyntaxWarning: invalid escape sequence` を抑制
  (alfworld archive code 文字列内の `\s`, `\{` 由来).

## 3. テスト結果

### 3.1 Phase 7e-3 専用 (`tests/test_phase7e3_agentsquare_search.py`)

| ゲート | テスト | 件数 | 結果 |
| --- | --- | --- | --- |
| import smoke | `test_import_phase7e3_modules` | 13 | PASS |
| prompts archive 件数 | `test_prompts_init_archives_sizes` | 1 | PASS |
| prompts entry pair | `test_prompts_get_prompt_returns_pair` | 1 | PASS |
| prompts feedback kwarg | `test_prompts_get_prompt_accepts_feedback_kwarg` | 1 | PASS |
| evolve DI | `test_evolve_with_mock_json_chat_fn` | 1 | PASS |
| recombine DI | `test_recombine_with_mock_chat_fn` | 1 | PASS |
| recombine fallback | `test_recombine_handles_malformed_response` | 1 | PASS |
| predictor DI | `test_predict_performance_with_mock_chat_fn` | 1 | PASS |
| predictor JSON fallback | `test_predict_performance_fallback_on_invalid_json` | 1 | PASS |
| archives 読み込み | `test_load_default_archives_returns_4_types` | 1 | PASS |
| run_search smoke | `test_run_search_with_mock_di_smoke` | 1 | PASS |
| 旧依存削除 (ast 検査) | `test_no_forbidden_imports` | 8 | PASS |

合計 **31/31 PASS**.

### 3.2 リグレッション

```
======================= 251 passed, 4 warnings in 1.27s ========================
```

Phase 7e-2 時点 220 件 + 7e-3 で新規 31 件 = **251/251 PASS**. 既存テストの破壊なし.
残 4 warnings は pydantic / mlflow / TestCase 衝突 (Phase 7e-3 と無関係, 既存).

### 3.3 ruff (scope: agentsquare + 7e-3 tests)

```
uv run ruff check src/tsumiki/policy/agentsquare/ tests/test_phase7e3_agentsquare_search.py
→ All checks passed!
```

vendored alfworld プロンプトの E501 は `per-file-ignores` で許容. 他は全て規約遵守.

## 4. 設計書 §6.2 ゲート充足状況

| ゲート | 状態 | 根拠 |
| --- | --- | --- |
| Vendoring 完了 (配置) | OK (7e-3) | evolution / recombination / predictor / search の 4 系統が `agentsquare/` 配下に配置 |
| **Vendoring 完了 (import)** | **OK (7e-3)** | 13 モジュール全て import 通過 (`import tsumiki.policy.agentsquare.{evolution,recombination,predictor,search,...}`) |
| **LLM 差し替え** | **OK** | ast 解釈で `from openai`, `from utils`, `import openai`, `import backoff`, `import tenacity` 全 0 件 (8 vendored ファイル分検査済) |
| ライセンス遵守 | OK | 各 vendored ファイル冒頭に Apache-2.0 derived from SHA `8f5b3fe5...` 明記 |
| 評価器 gate | 未着手 (7e-5) | - |
| `compose.run_compose` 動作 | 未着手 (7e-4) | - |
| 同一フレーム動作 | 未着手 (7e-6) | - |
| リグレッション | OK | 251/251 PASS |

## 5. 実装上の発見

| 項目 | 内容 |
| --- | --- |
| 上流の prompts シグネチャ不整合 | `module_evolution/prompt_X.py` は `get_prompt_X(archive)` だが `search/module_evolution.py` は `get_prompt_X(modules, last_feedback)` で呼ぶ. tsumiki は呼び出し側に合わせて `last_feedback=None` を許容する形に統一. |
| `inspect.getsource` 経路は alfworld 専用 | 上流 `module_predictor.py` は `inspect.getsource(class_name)` でモジュールのソースを取り出す設計だが, これは `modules_predictor/*` ファイルが必須. tsumiki では `archives[type]` の `code` フィールド (文字列) を直接利用する設計に変更. |
| alfworld archive code 文字列の `SyntaxWarning` | prompts ファイル本体の三重引用符付き docstring 内に正規表現 `\s` 等が含まれ Python 3.13 で警告. 文字列リテラルを raw 化すると上流 diff が大きくなるため `filterwarnings` で抑制. ファイル内容は実行されない. |
| `eval()` の置換 | 上流 `recombination.py`, `module_predictor.py` で LLM 応答に対する `eval()` 直接呼び出しが入っていた. 任意コード実行リスクのため tsumiki では `ast.literal_eval` / `json.loads` に統一. |
| alfworld 統合のロジック深度 | `agent_search.py` の `run_benchmark` は alfworld の `os.chdir`, `sys.path` 操作, ファイル書き出しを行う重い統合. tsumiki では `benchmark_fn` の単純な Callable に置換し, 上位層で評価器を差し込む設計に. |
| 上流のグローバル `client = openai.OpenAI(...)` | `module_evolution/module_evolution.py` トップレベルで `OPENAI_API_KEY` 環境変数経由のクライアント初期化が走るため, `import` 時点で副作用が発生する. tsumiki ではトップレベル副作用を全削除し, ChatFn を明示注入する形に. |

## 6. Phase 7e-4 への申し送り

設計書 §4 (`tsumiki.policy.compose` 仕様) を実装する際の前提:

1. **`ChatFn` / `JsonChatFn` の供給源は `tsumiki.llm` 拡張**:
   - 7d-3 の `make_openai_chat_fn` を流用. JSON mode 対応 `make_openai_json_chat_fn` を新規追加する必要がある (`response_format={"type": "json_object"}` 指定).
2. **`benchmark_fn` の実装**:
   - `compose.run_compose` 内で `evaluator_spec.implementation` (deterministic / generated evaluator) を呼ぶ wrapper を作る.
   - `Agent` dict (`{planning, reasoning, tooluse, memory}`) から実際の chat_fn (合成 policy) を組み立てる必要がある (Phase 7e-2 の `agentsquare.{planning,reasoning,memory,tooluse}` モジュールを使用).
3. **archives の domain 適応**:
   - 現状 `search/archives/*.json` は alfworld 由来. NDA / ISO27001 でも初期 archive として使えるが,
     ドメイン適応版を `archives/{nda,iso27001}/` 配下に作る案を検討 (Phase 7e-6 の試走結果次第).
4. **prompts の alfworld 固有部分**:
   - 上流 prompts の `# Task Overview: ALFworld is ...` 等は文字列温存しているが,
     compose ラッパでドメイン記述を **template に挿入する pre-processing 層** が必要 (現状は task_description 引数だけでは不足).
5. **`evolve()` 出力 code の `chat_fn` 化**:
   - 上流 LLM が生成する evolution code には `llm_response(...)` 形式の呼び出しが入る (上流 prompts の例示と一致). tsumiki ではこれを `chat_fn(...)` に書き換える後処理が必要 (Phase 7e-4 で compose ラッパ内に).

## 7. 関連

| 項目 | パス |
| --- | --- |
| Phase 7e 設計 | [`phase7e_design.md`](phase7e_design.md) |
| Phase 7e-1 結果 | [`phase7e1_vendoring_2026-06-19.md`](phase7e1_vendoring_2026-06-19.md) |
| Phase 7e-2 結果 | [`phase7e2_llm_swap_2026-06-19.md`](phase7e2_llm_swap_2026-06-19.md) |
| Vendoring 記録 | [`../agentsquare_vendoring.md`](../agentsquare_vendoring.md) |
| Vendored ファイル | [`../../src/tsumiki/policy/agentsquare/`](../../src/tsumiki/policy/agentsquare/) |
| Phase 7e-3 テスト | [`../../tests/test_phase7e3_agentsquare_search.py`](../../tests/test_phase7e3_agentsquare_search.py) |
