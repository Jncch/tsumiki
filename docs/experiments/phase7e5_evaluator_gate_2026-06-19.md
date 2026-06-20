# Phase 7e-5 結果: 評価器 gate 整理 (`is_approved()` + lookup/generator 経路 test)

実行日: 2026-06-19
設計書: [`phase7e_design.md`](phase7e_design.md) §4.3 / §6.2
前段: [`phase7e4_compose_2026-06-19.md`](phase7e4_compose_2026-06-19.md)

## 1. 結論先出し

| 項目 | 結果 |
| --- | --- |
| `EvaluatorSpec.is_approved()` メソッド追加 | 完了 (`approved_by != ""` の判定子, 1 行) |
| compose runner を `is_approved()` 経由に統一 | 完了 |
| lookup hit 経路 (store roundtrip) test | 追加 (2 件) |
| generator 経路 (デフォルト `approved_by="auto"`) test | 追加 (2 件) |
| 既存 generated 評価器の `approved_by` 設定確認 | 追加 (1 件) |
| **テスト** | **274/274 PASS** (Phase 7e-5 新規 11 件 + 既存 263 件) |
| ruff (specs.py + compose + 7e-5 tests) | All checks passed |

## 2. 実装内容

### 2.1 `EvaluatorSpec.is_approved()` 追加

設計書 §4.3 で示唆されていた `is_approved()` メソッドを `EvaluatorSpec` (`src/tsumiki/goal/specs.py`) に追加.

```python
def is_approved(self) -> bool:
    """評価器が承認済かを返す.

    CLAUDE.md §9 (評価器が無い状態で自動探索を回さない) の判定子.
    lookup hit (`approved_by="auto"`) または generator + verify 通過
    (`approved_by="<user>"`) で承認済とみなす.
    """
    return bool(self.approved_by)
```

### 2.2 `compose/runner.py` を `is_approved()` 経由に統一

7e-4 では `_assert_evaluator_gate_passed` 内で `if not evaluator_spec.approved_by:` と直接フィールド参照していたが, `EvaluatorSpec.is_approved()` メソッド経由に統一. 判定ロジックの所在を 1 か所に集中.

```python
if not evaluator_spec.is_approved():
    raise RuntimeError(...)
```

### 2.3 評価器が生まれる経路の確認

3 系統の経路 (lookup / generator / 既存 seed) で `approved_by` が正しく設定されることを確認:

| 経路 | 確認内容 | テスト |
| --- | --- | --- |
| **lookup hit** | `store.save` → `store.load` ラウンドトリップで `approved_by` が保持 | `test_store_roundtrip_preserves_approved_by` |
| **store load (空)** | `meta.yaml` に `approved_by` が無い場合は空文字扱い + gate raise | `test_store_load_treats_missing_approved_by_as_empty` |
| **generator (デフォルト)** | `generate_evaluator(...)` のデフォルト `approved_by="auto"` で gate 通過 | `test_generator_default_approved_by_is_auto` |
| **generator (明示空)** | `approved_by=""` で生成した spec は gate raise (人手承認待ち) | `test_generator_explicit_empty_approved_by_fails_gate` |
| **既存 seed** | `eval/generated/` 配下の全評価器が `approved_by` 設定済 | `test_existing_generated_evaluators_have_approved_by` |

最後の test は実ファイル (`eval/generated/{nda,iso27001}/.../meta.yaml`) を再帰検索して `is_approved()` を呼ぶ. Phase 7e-6 試走で `examples/{nda,iso27001}/run.sh --use-compose` が gate を通過するための前提を確認.

## 3. テスト結果

### 3.1 Phase 7e-5 専用 (`tests/test_phase7e5_evaluator_gate.py`)

| ゲート | テスト | 件数 | 結果 |
| --- | --- | --- | --- |
| `is_approved()` 単体 | `test_is_approved_judges_by_approved_by` | 4 | PASS |
| `is_approved()` truthiness | `test_is_approved_uses_truthiness` | 1 | PASS |
| compose gate 統合 | `test_assert_gate_uses_is_approved` | 1 | PASS |
| store roundtrip | `test_store_roundtrip_preserves_approved_by` | 1 | PASS |
| store 空 fallback | `test_store_load_treats_missing_approved_by_as_empty` | 1 | PASS |
| generator デフォルト | `test_generator_default_approved_by_is_auto` | 1 | PASS |
| generator 明示空 | `test_generator_explicit_empty_approved_by_fails_gate` | 1 | PASS |
| 既存 seed 確認 | `test_existing_generated_evaluators_have_approved_by` | 1 | PASS |

合計 **11/11 PASS**.

### 3.2 リグレッション

```
======================= 274 passed, 4 warnings in 1.29s ========================
```

Phase 7e-4 時点 263 件 + 7e-5 で新規 11 件 = **274/274 PASS**. 既存テストの破壊なし.

### 3.3 ruff

```
uv run ruff check src/tsumiki/goal/specs.py src/tsumiki/policy/compose/ tests/test_phase7e5_evaluator_gate.py
→ All checks passed!
```

## 4. 設計書 §6.2 ゲート充足状況

| ゲート | 状態 | 根拠 |
| --- | --- | --- |
| Vendoring (配置 + import) | OK (7e-1〜7e-3) | - |
| LLM 差し替え | OK (7e-2 / 7e-3) | - |
| ライセンス | OK | - |
| **評価器 gate** | **OK (7e-4 + 7e-5)** | `_assert_evaluator_gate_passed` + `EvaluatorSpec.is_approved()` + 3 経路で動作確認済 |
| **`compose.run_compose` 動作** | **OK (7e-4)** | - |
| 同一フレーム動作 | 未着手 (7e-6) | - |
| リグレッション | OK | 274/274 PASS |

## 5. 実装上の発見

| 項目 | 内容 |
| --- | --- |
| `store.save(root, spec)` のシグネチャ | `root` から `evaluator_dir(root, spec)` で domain / task_class / id に基づくサブディレクトリを内部で構築する. テスト書く際は `tmp_path` を直接渡せる. 7e-4 報告書時点の私の予想 (`save(spec, eval_dir)`) は誤り. |
| `store.load` の `approved_by` 復元 | `meta.get("approved_by", "")` で書かれており, 過去の互換性のため欠落も許容. ただし gate は空文字を未承認とみなして raise. |
| `generate_evaluator(..., approved_by="auto")` デフォルト | LLM 生成評価器が「自動承認 (=verify 通過後)」となる前提. 人手承認待ちなら `approved_by=""` を明示する形. |
| 既存 `eval/generated/` 配下の `approved_by` | 全 evaluator が `approved_by: jncch` で設定済 (Phase 5c / 6 で人手承認した記録). `test_existing_generated_evaluators_have_approved_by` で確認. |
| `is_approved()` の truthiness 判定 | 空白文字 (`" "`) も承認扱い (bool() の挙動と一致). 厳密化したい場合は `bool(self.approved_by.strip())` だが, 過剰実装と判断し採用見送り (7e-bonus で必要なら検討). |

## 6. Phase 7e-6 への申し送り

設計書 §5.2 / 7e-4 申し送り §6.2 の内容に変更なし. 以下を実装:

1. **`runner/e2e.py` に `use_compose` フラグ追加**:
   ```python
   class E2EConfig:
       use_compose: bool = False  # Phase 7e-6 で追加
       compose_max_depth: int = 3
   ```
2. **`benchmark_fn` の実装**:
   - 入力: `Agent` dict (`{planning, reasoning, tooluse, memory}`)
   - 処理: `agentsquare.{planning,reasoning,memory,tooluse}` から指定モジュールを取り出して合成 chat_fn を構築 → variant 実行 → 評価器スコア
   - 出力: `float`
3. **prompts への domain 適応**: `agentsquare/evolution/prompts/*.py` の alfworld 固有部分を NDA / ISO27001 に置換する pre-processing 層を `compose/runner.py` に追加
4. **archives の domain 適応**: 試走しつつ alfworld archive のまま使えるか確認. ダメなら `archives/{nda,iso27001}/` 新規作成
5. **`examples/{nda,iso27001}/run.sh` に `--use-compose` オプション**: bash 側で flag 解釈, `run_phase5c_dryrun.py` に伝搬
6. **試走**: NDA +0.261 ±0.05 / ISO27001 +0.029 ±0.05 (Phase 5c/6 baseline) を `--use-compose` 経由で再現確認

### 6.1 Phase 7-bonus への並行申し送り

Phase 7d-4 申し送り (CLI 引数復活, `LLMSettings.from_env_with_overrides()`) は 7e-6 試走前に実装することを推奨. 試走時の柔軟性向上.

## 7. 関連

| 項目 | パス |
| --- | --- |
| Phase 7e 設計 | [`phase7e_design.md`](phase7e_design.md) §4.3 |
| Phase 7e-1 結果 | [`phase7e1_vendoring_2026-06-19.md`](phase7e1_vendoring_2026-06-19.md) |
| Phase 7e-2 結果 | [`phase7e2_llm_swap_2026-06-19.md`](phase7e2_llm_swap_2026-06-19.md) |
| Phase 7e-3 結果 | [`phase7e3_search_2026-06-19.md`](phase7e3_search_2026-06-19.md) |
| Phase 7e-4 結果 | [`phase7e4_compose_2026-06-19.md`](phase7e4_compose_2026-06-19.md) |
| `EvaluatorSpec.is_approved()` 実装 | [`../../src/tsumiki/goal/specs.py`](../../src/tsumiki/goal/specs.py) |
| compose runner | [`../../src/tsumiki/policy/compose/runner.py`](../../src/tsumiki/policy/compose/runner.py) |
| Phase 7e-5 テスト | [`../../tests/test_phase7e5_evaluator_gate.py`](../../tests/test_phase7e5_evaluator_gate.py) |
