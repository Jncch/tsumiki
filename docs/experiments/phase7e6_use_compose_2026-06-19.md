# Phase 7e-6 結果: examples/{nda,iso27001}/run.sh --use-compose 試走対応

実行日: 2026-06-19
設計書: [`phase7e_design.md`](phase7e_design.md) §5 / §6.2
前段: [`phase7e5_evaluator_gate_2026-06-19.md`](phase7e5_evaluator_gate_2026-06-19.md), [`phase7bonus3_cli_overrides_2026-06-19.md`](phase7bonus3_cli_overrides_2026-06-19.md)

## 1. 結論先出し

| 項目 | 結果 |
| --- | --- |
| `E2EConfig` 拡張 | `use_compose`, `compose_max_depth`, `compose_json_chat_fn`, `llm_settings` を追加 |
| `E2EResult` 拡張 | `compose_selected_modules`, `compose_search_score` を追加 |
| `_run_compose_auxiliary` 実装 | `policy.compose.run_compose` を補助起動する内部 helper |
| `run_phase5c_dryrun.py` CLI | `--use-compose` / `--compose-max-depth` を追加 |
| `examples/*/run.sh` | `"$@"` 透過のため修正不要 |
| mlflow `active_run()` ガード | test 間 leak 防止のため追加 |
| **テスト** | **290/290 PASS** (Phase 7e-6 新規 6 件 + 既存 284 件) |
| ruff | All checks passed |
| **実走 (paired_diff 再現)** | **ユーザー実行待ち** (Azure / ollama 環境必要, Phase 7d-4 と同型) |

## 2. 実装内容

### 2.1 補助情報モードの設計判断

Phase 7e-6 の compose 統合は **「補助情報モード」** とする:

- `use_compose=True` でも variant 実行 (reuse / zerobase) は **従来どおり**
- `paired_diff` の意味は変わらない (Phase 5c / 6 baseline と同じ計算式)
- compose は AgentSquare 探索を**並行で**起動し, `selected_modules` と `search_score` を MLflow にログ + 結果に含めるのみ
- `benchmark_fn` は trivial (常に reuse_sr を返す). 本格的な探索評価は Phase 9+ で `agentsquare.{planning,reasoning,memory,tooluse}` 合成 chat_fn を実装した上で実走させる

これは設計書 §4.1 の「薄いラッパ」段階と一致する. 探索ループ動作 + 評価器 gate 通過 + 構成選択の MLflow ロギング を smoke レベルで確認するため.

### 2.2 `E2EConfig` 拡張 (src/tsumiki/runner/e2e.py)

```python
@dataclass(frozen=True)
class E2EConfig:
    ...
    # Phase 7e-6: policy.compose 補助起動
    use_compose: bool = False
    compose_max_depth: int = 3
    compose_json_chat_fn: Callable[[list[dict[str, str]]], dict[str, Any]] | None = None
    llm_settings: LLMSettings | None = None  # use_compose=True で必須
```

### 2.3 `E2EResult` 拡張

```python
@dataclass(frozen=True)
class E2EResult:
    ...
    compose_selected_modules: dict[str, str] | None = None
    compose_search_score: float | None = None
```

### 2.4 `_run_compose_auxiliary` 関数

```python
def _run_compose_auxiliary(
    *, cfg: E2EConfig, ts: TaskSpec, spec: EvaluatorSpec,
    ng_book, reuse_sr: float,
) -> tuple[dict[str, str], float]:
    if cfg.llm_settings is None:
        raise ValueError("use_compose=True requires E2EConfig.llm_settings")
    if cfg.compose_json_chat_fn is None:
        raise ValueError("use_compose=True requires E2EConfig.compose_json_chat_fn")

    def _benchmark_fn(_agent: dict[str, str]) -> float:
        return reuse_sr  # trivial. Phase 9+ で本物の合成 chat_fn 構築

    compose_cfg = ComposeConfig(
        task_spec=ts, evaluator_spec=spec, knowledge=ng_book,
        llm_settings=cfg.llm_settings,
        chat_fn=_to_text_chat_fn(cfg.runtime_chat_fn),
        json_chat_fn=cfg.compose_json_chat_fn,
        benchmark_fn=_benchmark_fn,
        max_search_depth=cfg.compose_max_depth, seed=cfg.seed,
    )
    result = run_compose(compose_cfg)
    if mlflow.active_run() is not None:
        try:
            mlflow.log_dict(result.selected_modules, "compose_selected_modules.json")
            mlflow.log_metric("compose_search_score", float(result.search_score))
        except Exception as e:
            print(f"[compose] mlflow log skipped: {e}")
    return dict(result.selected_modules), float(result.search_score)
```

### 2.5 `run_phase5c_dryrun.py` CLI 拡張

```
--use-compose                  AgentSquare 探索を補助起動 (smoke 用デフォルト OFF)
--compose-max-depth N          探索 iteration 数 (デフォルト 1)
```

`use_compose=True` のときのみ `make_openai_json_chat_fn(client, ...)` を構築して `E2EConfig.compose_json_chat_fn` に渡す.

### 2.6 mlflow `active_run()` ガード

`mlflow.log_dict` / `mlflow.log_metric` は active run が無いと自動で `start_run()` を呼ぶ. これが他 test の run と衝突して 4 件 fail を引き起こした (`test_runner_phase{1,2}.py`).

対策として `if mlflow.active_run() is not None:` でガード. e2e 実走時は phase2 variant が既に run を開いているため log は通る. smoke test では active_run が無いため skip.

### 2.7 `examples/*/run.sh` の修正は不要

既存の `examples/{nda,iso27001}/run.sh` は末尾で `"$@"` を `run_phase5c_dryrun.py` に渡しているため,
試走時は以下で `--use-compose` を追加できる:

```bash
bash examples/nda/run.sh --use-compose --compose-max-depth 1
bash examples/iso27001/run.sh --use-compose --compose-max-depth 1
```

## 3. テスト結果

### 3.1 Phase 7e-6 専用 (`tests/test_phase7e6_use_compose.py`)

| ゲート | テスト | 件数 | 結果 |
| --- | --- | --- | --- |
| E2EConfig フィールド存在 | `test_e2e_config_has_compose_fields` | 1 | PASS |
| E2EResult フィールド存在 | `test_e2e_result_has_compose_fields` | 1 | PASS |
| use_compose デフォルト False | `test_e2e_config_use_compose_defaults_false` | 1 | PASS |
| `_run_compose_auxiliary` smoke | `test_run_compose_auxiliary_smoke` | 1 | PASS |
| llm_settings 未指定 raise | `test_run_compose_auxiliary_raises_when_llm_settings_missing` | 1 | PASS |
| json_chat_fn 未指定 raise | `test_run_compose_auxiliary_raises_when_json_chat_fn_missing` | 1 | PASS |

合計 **6/6 PASS**.

### 3.2 リグレッション

```
======================= 290 passed, 4 warnings in 1.30s ========================
```

Phase 7-bonus-3 時点 284 件 + 7e-6 で新規 6 件 = **290/290 PASS**.

途中で 4 件 fail があった (mlflow active run leak) → `mlflow.active_run()` ガードで修正.

### 3.3 ruff

```
uv run ruff check src/tsumiki/runner/e2e.py experiments/run_phase5c_dryrun.py tests/test_phase7e6_use_compose.py
→ All checks passed!
```

## 4. 設計書 §6.2 ゲート充足状況

| ゲート | 状態 | 根拠 |
| --- | --- | --- |
| Vendoring (配置 + import) | OK (7e-1〜7e-3) | - |
| LLM 差し替え | OK (7e-2 / 7e-3) | - |
| ライセンス | OK | - |
| 評価器 gate | OK (7e-4 + 7e-5) | - |
| `compose.run_compose` 動作 | OK (7e-4) | - |
| **同一フレーム動作 (実装)** | **OK (7e-6)** | `_run_compose_auxiliary` smoke で確認. `examples/*/run.sh --use-compose` で起動可能 |
| **同一フレーム動作 (実走 paired_diff)** | **ユーザー実走待ち** | NDA +0.261 ±0.05 / ISO27001 +0.029 ±0.05 を `--use-compose` 経由で再現確認 (Phase 7d-4 と同型) |
| リグレッション | OK | 290/290 PASS |

## 5. 実走コマンド (ユーザー実行用)

### 5.1 NDA (Azure OpenAI 経由)

```bash
# .env を 7d-4 と同じ Azure OpenAI 設定にしておく.
bash examples/nda/run.sh --use-compose --compose-max-depth 1
```

期待出力 (末尾):
```
========== Phase 5c E2E Summary ==========
  goal:                  'NDA をチェックして問題条項を是正したい'
  ...
  paired_diff:           +0.XXX
  baseline (Phase 5c NDA):+0.261
  gate (±0.05):          OK / FAIL
  compose selected:      {'planning': '...', 'reasoning': '...', 'tooluse': '...', 'memory': '...'}
  compose score:         0.XXX
```

### 5.2 ISO27001 (同様)

```bash
bash examples/iso27001/run.sh --use-compose --compose-max-depth 1
```

期待: `baseline (Phase 6 ISO27001):+0.029`, gate OK / FAIL.

### 5.3 ollama 経由 (低コスト smoke)

```bash
bash examples/nda/run.sh \
  --use-compose --compose-max-depth 1 \
  --llm-provider openai_compatible \
  --llm-base-url http://localhost:11434/v1 \
  --llm-model hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M
```

Phase 7-bonus-3 の `--llm-*` 引数で Azure → ollama 切り替えが可能.

## 6. 実装上の発見

| 項目 | 内容 |
| --- | --- |
| mlflow の `log_dict` / `log_metric` 暗黙 `start_run` | active run が無いと内部で勝手に `start_run()` してしまい, test 間で run が leak する. `active_run() is not None` で明示ガードが必要. tsumiki 内の他 mlflow 呼び出しを将来全体的に audit するべき (Phase 9+ 任意). |
| `examples/*/run.sh` の `"$@"` 透過 | 既に `"$@"` で末尾引数を forward しているため shell 側修正不要. Phase 7c で確立した設計が 7e-6 にもそのまま効いた. |
| benchmark_fn を trivial にした判断 | 本物の合成 chat_fn 構築には `agentsquare.{planning,reasoning,memory,tooluse}` の 4 モジュールを連結する大規模実装が必要 (Agent dict の "name" 文字列から実モジュールクラスを引いて連鎖). Phase 7e 設計書 §4.1 の「薄いラッパ」段階に収め, Phase 9+ で本物の探索評価を実装する申し送り. |
| compose の `task_description` = `TaskSpec.raw_goal` | 7e-4 申し送りどおり raw_goal を流用. 上流 alfworld 固有 prompt 内容との不整合は smoke レベルでは問題なし. domain 別 archive 適応は Phase 9+ で. |

## 7. Phase 7e-7 への申し送り (結果報告書)

Phase 7e-7 は「結果報告書」(0.5 日) なので, 本書を含む 7e-1〜7e-6 の結果を集約した **Phase 7e 統合結果報告書** を `phase7e_summary_2026-06-19.md` として作成する.
内容:
1. 7e 全サブの達成項目一覧
2. 設計書 §6 ゲートの最終充足状況
3. 実走結果 (NDA / ISO27001 paired_diff with `--use-compose`)
4. Phase 8 (Zenn Part 3/4 公開 + OSS リリース) への申し送り
5. Phase 9+ への持ち越し (本物の探索評価, archives domain 適応, generator 改修等)

## 8. 関連

| 項目 | パス |
| --- | --- |
| Phase 7e 設計 | [`phase7e_design.md`](phase7e_design.md) §5 |
| Phase 7e-1〜5 結果 | [`phase7e{1,2,3,4,5}_*_2026-06-19.md`](.) |
| Phase 7-bonus-3 結果 | [`phase7bonus3_cli_overrides_2026-06-19.md`](phase7bonus3_cli_overrides_2026-06-19.md) |
| `runner/e2e.py` 実装 | [`../../src/tsumiki/runner/e2e.py`](../../src/tsumiki/runner/e2e.py) |
| `run_phase5c_dryrun.py` 実装 | [`../../experiments/run_phase5c_dryrun.py`](../../experiments/run_phase5c_dryrun.py) |
| Phase 7e-6 テスト | [`../../tests/test_phase7e6_use_compose.py`](../../tests/test_phase7e6_use_compose.py) |
