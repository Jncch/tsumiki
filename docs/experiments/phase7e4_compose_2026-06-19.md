# Phase 7e-4 結果: tsumiki.policy.compose 薄いラッパ実装 + 評価器 gate

実行日: 2026-06-19
設計書: [`phase7e_design.md`](phase7e_design.md) §4 / §6
前段: [`phase7e3_search_2026-06-19.md`](phase7e3_search_2026-06-19.md)

## 1. 結論先出し

| 項目 | 結果 |
| --- | --- |
| ComposeConfig / ComposeResult | 完了 (frozen dataclass) |
| `_assert_evaluator_gate_passed` | 完了 (`approved_by` 空で `RuntimeError`) |
| `run_compose(cfg)` | 完了 (評価器 gate → AgentSquare 探索 → `ComposeResult`) |
| `make_openai_json_chat_fn` | 完了 (`tsumiki.data.synthesis` に追加) |
| **import 通過** | **OK** |
| **テスト** | **263/263 PASS** (Phase 7e-4 新規 12 件 + 既存 251 件) |
| ruff (compose + synthesis + 7e-4 tests) | All checks passed |

## 2. 実装内容

### 2.1 配置

| ファイル | 内容 | 行数 |
| --- | --- | --- |
| `src/tsumiki/policy/compose/__init__.py` | 公開 API の re-export (`ComposeConfig`, `ComposeResult`, `run_compose`, `_assert_evaluator_gate_passed`) | 26 |
| `src/tsumiki/policy/compose/config.py` | `ComposeConfig` / `ComposeResult` (frozen dataclass) + 3 種類の Callable 型 (`ChatFn` / `JsonChatFn` / `BenchmarkFn`) | 65 |
| `src/tsumiki/policy/compose/runner.py` | `_assert_evaluator_gate_passed` + `run_compose(cfg)` | 60 |
| `src/tsumiki/data/synthesis.py` | `make_openai_json_chat_fn` を追記 (JSON mode 用 chat fn supplier) | +47 (既存 313 行) |

### 2.2 `ComposeConfig` (frozen dataclass)

```python
@dataclass(frozen=True)
class ComposeConfig:
    task_spec: TaskSpec
    evaluator_spec: EvaluatorSpec
    knowledge: NGPatternBook
    llm_settings: LLMSettings
    chat_fn: ChatFn
    json_chat_fn: JsonChatFn
    benchmark_fn: BenchmarkFn
    max_search_depth: int = 3
    seed: int = 42
```

設計書 §4.2 の仕様に, 7e-3 で確定した 3 種 DI (`ChatFn` / `JsonChatFn` / `BenchmarkFn`) を追加.
`runtime_chat_fn` フィールドは `ComposeResult` ではなく入力側に置く方針に変更 (探索は構成選択を返すのみで, 実行時 chat_fn は呼び出し側が `agentsquare.{planning,reasoning,memory,tooluse}` から自前で組み立てる責任).

### 2.3 `ComposeResult` (frozen dataclass)

```python
@dataclass(frozen=True)
class ComposeResult:
    selected_modules: dict[str, str]
    search_score: float
    search_history: list[dict[str, Any]] = field(default_factory=list)
    test_counts: dict[str, Any] = field(default_factory=dict)
```

### 2.4 `_assert_evaluator_gate_passed` (評価器 gate)

```python
def _assert_evaluator_gate_passed(evaluator_spec: EvaluatorSpec) -> None:
    if not evaluator_spec.approved_by:
        raise RuntimeError(
            f"evaluator {evaluator_spec.id!r} is not approved "
            f"(approved_by is empty); must pass goal/lookup or "
            f"goal/verifier before compose"
        )
```

CLAUDE.md §9 (評価器が無い状態で自動探索を回さない) を体現. `EvaluatorSpec.approved_by != ""` で承認済を判定 (Phase 5c の lookup hit は `approved_by="auto"`, generator + verify 通過は `approved_by="user"` 等).

### 2.5 `run_compose` (薄いラッパ)

```python
def run_compose(cfg: ComposeConfig) -> ComposeResult:
    _assert_evaluator_gate_passed(cfg.evaluator_spec)
    task_description = cfg.task_spec.raw_goal or (
        f"{cfg.task_spec.domain} / {cfg.task_spec.task_class}"
    )
    result = run_search(
        benchmark_fn=cfg.benchmark_fn,
        chat_fn=cfg.chat_fn,
        json_chat_fn=cfg.json_chat_fn,
        task_description=task_description,
        num_iterations=cfg.max_search_depth,
        output_dir=None,
    )
    return ComposeResult(
        selected_modules=dict(result["best_agent"]),
        search_score=float(result["best_performance"]),
        search_history=list(result["tested_cases"]),
        test_counts=dict(result["test_counts"]),
    )
```

設計書 §4.2 の仕様に従い:
1. 評価器 gate 強制
2. AgentSquare `run_search` を呼び出し
3. 結果を `ComposeResult` に詰めて返す

`task_description` は `TaskSpec.raw_goal` を流用 (Phase 7e-3 申し送り §6.4 のドメイン適応は Phase 7e-6 で対応).

### 2.6 `make_openai_json_chat_fn` (JSON mode supplier)

```python
def make_openai_json_chat_fn(
    client, model: str, temperature: float, seed: int,
    max_completion_tokens: int = 4096, num_ctx: int | None = None,
) -> Callable[[list[dict[str, str]]], dict]:
    ...
    def call(messages: list[dict[str, str]]) -> dict:
        kwargs = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        ...
        content = resp.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}
    return call
```

`make_openai_chat_fn` (Phase 7d-4) と同型 (`is_reasoning_model`, `num_ctx`, `extra_body` の取り扱いを揃える). 戻り値が `ChatResult` (text) ではなく `dict` (parsed JSON) のみ違い. AgentSquare evolution の `JsonChatFn` 型と一致.

## 3. テスト結果

### 3.1 Phase 7e-4 専用 (`tests/test_phase7e4_compose.py`)

| ゲート | テスト | 件数 | 結果 |
| --- | --- | --- | --- |
| import smoke | `test_import_compose_modules` | 3 | PASS |
| 公開 API 存在 | `test_compose_public_api_exists` | 1 | PASS |
| ComposeConfig frozen | `test_compose_config_is_frozen` | 1 | PASS |
| ComposeResult frozen | `test_compose_result_is_frozen` | 1 | PASS |
| 評価器 gate (承認済) | `test_assert_evaluator_gate_passed_with_approved` | 1 | PASS |
| 評価器 gate (未承認 raise) | `test_assert_evaluator_gate_passed_raises_when_empty` | 1 | PASS |
| run_compose 未承認 raise | `test_run_compose_raises_when_evaluator_not_approved` | 1 | PASS |
| run_compose smoke (mock DI) | `test_run_compose_returns_result_with_mock_di` | 1 | PASS |
| json_chat_fn Callable | `test_make_openai_json_chat_fn_returns_callable` | 1 | PASS |
| json_chat_fn JSON parse 失敗 | `test_make_openai_json_chat_fn_handles_invalid_json` | 1 | PASS |

合計 **12/12 PASS**.

### 3.2 リグレッション

```
======================= 263 passed, 4 warnings in 1.34s ========================
```

Phase 7e-3 時点 251 件 + 7e-4 で新規 12 件 = **263/263 PASS**. 既存テストの破壊なし.

### 3.3 ruff (scope: compose + synthesis + 7e-4 tests)

```
uv run ruff check src/tsumiki/policy/compose/ src/tsumiki/data/synthesis.py tests/test_phase7e4_compose.py
→ All checks passed!
```

## 4. 設計書 §6.2 ゲート充足状況

| ゲート | 状態 | 根拠 |
| --- | --- | --- |
| Vendoring 完了 (配置 + import) | OK (7e-1〜7e-3) | - |
| LLM 差し替え | OK (7e-2 / 7e-3) | - |
| ライセンス遵守 | OK (7e-1〜7e-3) | - |
| **評価器 gate** | **OK (7e-4)** | `test_assert_evaluator_gate_passed_raises_when_empty` で `RuntimeError` 動作確認 |
| **`compose.run_compose` 動作** | **OK (7e-4)** | mock chat_fn + benchmark_fn で `ComposeResult` が返ることを確認 |
| 同一フレーム動作 | 未着手 (7e-6) | - |
| リグレッション | OK | 263/263 PASS |

## 5. 実装上の決定事項

| 項目 | 内容 |
| --- | --- |
| `ComposeResult.runtime_chat_fn` フィールドは置かない | 設計書 §4.2 案の `runtime_chat_fn` は除外. 探索の責務は **構成選択** のみ. 実行時 chat_fn は呼び出し側が `agentsquare.{planning,reasoning,memory,tooluse}` から組み立てる責任. 単一責任原則と一致. |
| `task_description = TaskSpec.raw_goal` 流用 | 上流の alfworld ハードコードを引数化したが, ドメイン別 archive 適応は Phase 7e-6 に持ち越し. raw_goal が空のときは `{domain} / {task_class}` で fallback. |
| `Knowledge` を ComposeConfig に含めたが現状未使用 | 設計書 §4.2 の仕様に含めたが, `run_compose` 内部では参照しない. Phase 7e-6 で prompts の task_description template に挿入する pre-processing で使う想定. 過剰実装回避のため現状は dataclass フィールドだけ確保. |
| `make_openai_json_chat_fn` は `make_openai_chat_fn` の双子実装 | 戻り値が `dict` 専用な点だけ違う. `is_reasoning_model` 判定や `num_ctx` 取り扱いは完全同型. メンテ時に両方更新する必要がある (Phase 9+ で `make_openai_*_fn` を 1 つに統合検討). |

## 6. Phase 7e-5 / 7e-6 への申し送り

### 6.1 Phase 7e-5 (評価器 gate 実装 + unit test)

7e-4 で既に `_assert_evaluator_gate_passed` の unit test 2 件 (承認済 / 未承認) を導入済.
7e-5 では以下を追加:

1. **EvaluatorSpec.is_approved() メソッド追加検討**: 設計書 §4.3 の API として `is_approved()` メソッドを `EvaluatorSpec` に追加するか, 関数として外出しするか. 現状 `approved_by != ""` の判定子 1 行なので必須ではない.
2. **goal/lookup hit パスの確認**: `goal/lookup` 経由で得た EvaluatorSpec が `approved_by="auto"` で gate を通過することを試走で確認 (Phase 5c の e2e で動作実績あり).
3. **generator + verify 通過パスの確認**: `goal/generator` + `goal/verifier` 通過後の EvaluatorSpec が `approved_by="user"` (or "auto") に設定されていることを確認.

### 6.2 Phase 7e-6 (examples/{nda,iso27001}/run.sh --use-compose 試走)

7e-6 では以下を実装:

1. **`runner/e2e.py` に `use_compose` フラグ追加**: 設計書 §5.2 のとおり, `E2EConfig.use_compose: bool = False` を追加し, `True` 時は `compose.run_compose(...)` を起動.
2. **`benchmark_fn` の実装**:
   - 入力: `Agent` dict (`{planning, reasoning, tooluse, memory}`)
   - 処理: `agentsquare.{planning,reasoning,memory,tooluse}` から指定モジュールを取り出して合成 chat_fn を構築 → `data/synthesis` で variant 実行 → `eval/runners` で評価 → スカラー score を返す
   - 出力: `float` (paired_diff 等の主指標)
3. **prompts への domain 適応**: `agentsquare/evolution/prompts/*.py` の alfworld 固有部分を NDA / ISO27001 に置換する pre-processing 層を `compose/runner.py` に追加.
4. **archives の domain 適応**:
   - 現状 `agentsquare/search/archives/*.json` は alfworld 由来. NDA / ISO27001 用の初期 archive を `archives/{nda,iso27001}/` 配下に新規作成するか, alfworld archive のまま動作することを試走で確認.
5. **`examples/{nda,iso27001}/run.sh` に `--use-compose` オプション追加**: 既存の `--baseline-paired-diff` と同様に bash 側で flag 解釈.
6. **試走 with paired_diff 確認**: NDA +0.261 ±0.05 / ISO27001 +0.029 ±0.05 (Phase 5c/6 baseline) を `--use-compose` 経由でも再現することを確認.

### 6.3 Phase 7-bonus への申し送り (CLI 引数復活)

Phase 7d-4 でユーザー要望「`LLMSettings.from_env_with_overrides()` CLI 復活」が未着手.
Phase 7e-6 試走前に `LLMSettings.from_env_with_overrides()` を実装し, `--llm-provider` / `--llm-model` 等の CLI 引数で `.env` を上書きできるようにする (試走時の柔軟性向上).

## 7. 関連

| 項目 | パス |
| --- | --- |
| Phase 7e 設計 | [`phase7e_design.md`](phase7e_design.md) §4 |
| Phase 7e-1 結果 | [`phase7e1_vendoring_2026-06-19.md`](phase7e1_vendoring_2026-06-19.md) |
| Phase 7e-2 結果 | [`phase7e2_llm_swap_2026-06-19.md`](phase7e2_llm_swap_2026-06-19.md) |
| Phase 7e-3 結果 | [`phase7e3_search_2026-06-19.md`](phase7e3_search_2026-06-19.md) |
| compose 実装 | [`../../src/tsumiki/policy/compose/`](../../src/tsumiki/policy/compose/) |
| Phase 7e-4 テスト | [`../../tests/test_phase7e4_compose.py`](../../tests/test_phase7e4_compose.py) |
