# Phase 7e-2 結果: AgentSquare LLM 差し替え + langchain 削除 + import smoke

実行日: 2026-06-19
設計書: [`phase7e_design.md`](phase7e_design.md) §3 / §6
前段: [`phase7e1_vendoring_2026-06-19.md`](phase7e1_vendoring_2026-06-19.md)

## 1. 結論先出し

| 項目 | 結果 |
| --- | --- |
| LLM 呼び出し差し替え | 完了. 4 ファイル全てで `from utils import llm_response` 削除, `chat_fn` (DI) 経路に統一 |
| langchain 削除 | 完了. `OpenAIEmbeddings` / `Chroma` / `Document` の依存を全削除. memory は in-memory `_SimpleMemoryStore` で代替 |
| タスク固有 import 削除 | 完了. `planning_prompt` / `tooluse_IO_pool` を外部注入 (`few_shot` 引数, `tool_pool` 引数) に置換 |
| 削除した variant | `ToolUseToolBench`, `ToolUseToolBenchFormer` (langchain Chroma embedding 検索, tsumiki では `tsumiki.tools` で代替予定) |
| **import 通過** | **OK**. `import tsumiki.policy.agentsquare.{memory,planning,reasoning,tooluse}` 全 PASS |
| **テスト** | **220/220 PASS** (Phase 7e-2 新規 19 件 + 既存 201 件) |
| ruff (agentsquare) | All checks passed (E501 のみ per-file ignore で許容) |
| pyproject.toml exclude | 解除済 (agentsquare は通常 lint / type check に乗る) |

## 2. 実装内容

### 2.1 共通変更パターン (4 ファイル)

```python
# Before (上流)
from utils import llm_response

class XxxBase:
    def __init__(self, llms_type):
        self.llm_type = llms_type[0]

    def __call__(self, ...):
        result = llm_response(prompt=p, model=self.llm_type, temperature=0.1, ...)

# After (tsumiki)
from collections.abc import Callable
ChatFn = Callable[[str], str]

class XxxBase:
    def __init__(self, chat_fn: ChatFn, llms_type: list[str] | None = None) -> None:
        self.llm_type = llms_type[0] if llms_type else ""
        self._chat_fn = chat_fn

    def __call__(self, ...):
        result = self._chat_fn(prompt)
```

- `llms_type` は後方互換のため引数で受けるが内部では使わない (`chat_fn` 内の `settings.model` で完結)
- `temperature` / `stop_strs` 引数は ChatFn に直接渡せないため:
  - `temperature` は `LLMSettings.temperature` (`.env`) で外部設定
  - `stop_strs=['\n']` は ChatFn 戻り値を `.split('\n')[0]` で代替 (`_chat_then_strip` ヘルパ)
- `n=5`, `n=3` の複数サンプリングは ChatFn を n 回呼ぶループで代替 (`_sample` ヘルパ)

### 2.2 ファイル別変更

#### planning.py

- 7 クラス (PlanningBase, IO, DEPS, TD, Voyager, OPENAGI, HUGGINGGPT) 保持
- `from planning_prompt import *` を削除
- `__call__` のシグネチャに `few_shot: str` を追加 (外部から例文を注入)
- 各 `create_prompt` の英語プロンプト本文は **上流のまま保持** (alfworld 想定. ドメイン非依存化は Phase 7e-4 で必要に応じて差し替え)

#### reasoning.py

- 9 クラス (Base, IO, COT, COTSC, TOT, DILU, SelfRefine, StepBack, SelfReflectiveTOT) 保持
- `_chat_then_strip` / `_sample` ヘルパを Base に追加
- ReasoningDILU の system + user 2-role メッセージは concat して単一 prompt に
- `process_task_description` の alfworld 固有挙動 (`'Your task is to:'`, `'You are in the'`) は **形を保持**

#### memory.py

- 5 クラス (Base, DILU, Generative, TP, Voyager) 保持
- `langchain_openai.OpenAIEmbeddings`, `langchain_chroma.Chroma`, `langchain.docstore.document.Document` を **削除**
- `_SimpleMemoryStore` を新規追加 (langchain Chroma の代替, semantic 検索ではなく substring 一致 + 最新順)
- 永続化 (`shutil`, `os.path`, `./db`) を削除 (in-memory 化)

#### tooluse.py

- **削除**: `ToolUseToolBench`, `ToolUseToolBenchFormer` (langchain Chroma 依存重く, tsumiki では `tsumiki.tools` で代替)
- 残り 4 クラス (Base, IO, AnyTool, ToolFormer) を保持
- `from tooluse_IO_pool import tooluse_IO_pool` を削除
- `__init__` で `tool_pool: dict[str, str] | None = None` を外部から受け取る

### 2.3 `agentsquare/__init__.py` 更新

```python
from tsumiki.policy.agentsquare import memory, planning, reasoning, tooluse

__all__ = ["memory", "planning", "reasoning", "tooluse"]
```

### 2.4 `pyproject.toml` 更新

- Phase 7e-1 の暫定 `extend-exclude` / `exclude` (ruff / pyright) を削除
- vendored の英語プロンプト長行 (E501) は `per-file-ignores` で許容:

```toml
[tool.ruff.lint]
per-file-ignores = { "src/tsumiki/policy/agentsquare/*.py" = ["E501"] }
```

## 3. テスト結果

### 3.1 Phase 7e-2 専用 (`tests/test_phase7e_agentsquare.py`)

| ゲート | テスト | 件数 | 結果 |
| --- | --- | --- | --- |
| import smoke | `test_import_agentsquare_modules` | 5 | PASS |
| Base 初期化 (chat_fn DI) | `test_*_base_init_with_chat_fn` | 4 | PASS |
| variant 存在確認 | `test_*_variants_exist` | 4 | PASS |
| 旧依存削除 | `test_no_langchain_or_utils_import` | 4 | PASS |
| `_SimpleMemoryStore` 基本動作 | `test_simple_memory_store_basic_ops` | 1 | PASS |
| ChatFn DI 動作 | `test_planning_io_call_uses_chat_fn` | 1 | PASS |

合計 **19/19 PASS**.

### 3.2 リグレッション

```
======================= 220 passed, 4 warnings in 1.64s ========================
```

Phase 7e-1 時点 201 件 + 7e-2 で新規 19 件 = **220/220 PASS**. 既存テストの破壊なし.

### 3.3 ruff / pyright

```
uv run ruff check src/tsumiki/policy/agentsquare/
→ All checks passed!
```

`pyproject.toml` の暫定 exclude 解除済. agentsquare は通常 lint / type check に乗る状態.

## 4. 設計書 §6.2 ゲート充足状況

| ゲート | 状態 | 根拠 |
| --- | --- | --- |
| Vendoring 完了 (配置) | OK (7e-1) | 4 ファイル + LICENSE 配置 |
| **Vendoring 完了 (import)** | **OK (7e-2)** | `import tsumiki.policy.agentsquare.{memory,planning,reasoning,tooluse}` 通過 |
| **LLM 差し替え** | **OK** | `from openai import OpenAI` / `from utils import llm_response` の直接呼び出しが 4 ファイルで **0 件** |
| ライセンス遵守 | OK | LICENSE / NOTICE / 各ファイル冒頭の vendoring docstring に Apache-2.0 derived from <SHA> 明記 |
| 評価器 gate | 未着手 (7e-5) | - |
| `compose.run_compose` 動作 | 未着手 (7e-4) | - |
| 同一フレーム動作 | 未着手 (7e-6) | - |
| リグレッション | OK | 220/220 PASS |

## 5. 実装上の発見

| 項目 | 内容 |
| --- | --- |
| Reasoning の `process_task_description` が alfworld 固有 | `'Your task is to:'`, `'You are in the'` 等の固有文字列に依存. NDA / ISO27001 では実走できない. ドメイン非依存化は Phase 7e-4 (compose ラッパでドメイン別前処理を注入) で対応 |
| Planning の `__call__` 戻り値が `ast.literal_eval` 依存 | dict 形式の出力が前提. mock chat_fn では dict が含まれず空 list が返る. これは想定動作 |
| ToolBench 系の削除 | langchain Chroma 経由の semantic 検索を tsumiki に持ち込まない方針 (Phase 7a §5.2 と整合). 代替は Phase 7e-3 で `tsumiki.tools` プラグインまたは `_SimpleMemoryStore` で対応 |
| 上流 `temperature=0.1` 等のハードコード | ChatFn は `LLMSettings.temperature` (`.env`) を内部で使うため, vendored 側の `temperature` 引数は無視. 厳密な再現が必要なら Phase 9+ で per-call temperature を ChatFn に渡せる拡張を検討 |

## 6. Phase 7e-3 への申し送り

7e-3 で `module_evolution/`, `module_recombination/`, `module_predictor/`, `search/` を取り込み:

1. **上流依存の事前把握**: 7e-1 と同様に, 取り込み前に依存ファイル (`tasks/*/utils.py`, prompts 等) を確認
2. **LLM 呼び出し差し替え方針は 7e-2 と同型**: `chat_fn` を コンストラクタで DI, `llm_response` を全削除
3. **評価器呼び出し部の書き換え**: 上流の評価器コールを tsumiki の `eval/generated/<domain>/<task_class>/<id>/` lookup に差し替え
4. **alfworld 固有部分のスキップ**: ベンチマーク統合 (`tasks/alfworld/eval_*.py` 等) は取り込まず, 関連箇所を pragma コメントで明示
5. **lint per-file-ignore は引き継ぐ**: 同じ `src/tsumiki/policy/agentsquare/**.py` 系 path で `E501` 等を許容

## 7. 関連

| 項目 | パス |
| --- | --- |
| Phase 7e 設計 | [`phase7e_design.md`](phase7e_design.md) |
| Phase 7e-1 結果 | [`phase7e1_vendoring_2026-06-19.md`](phase7e1_vendoring_2026-06-19.md) |
| Vendoring 記録 | [`../agentsquare_vendoring.md`](../agentsquare_vendoring.md) |
| Vendored ファイル | [`../../src/tsumiki/policy/agentsquare/`](../../src/tsumiki/policy/agentsquare/) |
| Phase 7e-2 テスト | [`../../tests/test_phase7e_agentsquare.py`](../../tests/test_phase7e_agentsquare.py) |
