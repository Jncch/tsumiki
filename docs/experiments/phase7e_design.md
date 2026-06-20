# Phase 7e 設計: AgentSquare partial vendoring と policy/compose ラッパ

本書は Phase 7e の事前設計 (実行前の合格条件・vendoring 範囲・LLM 呼び出し差し替え方針を後出ししないため).
実装後の結果は別途 `phase7e_compose_<date>.md` に記録する.

前段:
- 全体方針: [`phase7_design.md`](phase7_design.md) §1 (7e) / §2 / §6.5
- 上流調査: [`phase7a_agentsquare_2026-06-19.md`](phase7a_agentsquare_2026-06-19.md) §3-§7
- 7d 観測 (申し送り取り込み): [`phase7d_provider_and_generator_2026-06-19.md`](phase7d_provider_and_generator_2026-06-19.md) §8

## 0. 目的と位置づけ

### 0.1 目的

Phase 7a で確定した **方針 B-2 (partial vendoring)** を実装に落とし, AgentSquare の制約付きモジュール探索 (Planning / Reasoning / Tool Use / Memory) を `tsumiki.policy.compose` 経由で起動できる状態にする.

これにより以下を達成:

- `examples/{nda,iso27001}/run.sh` が **`policy.compose` 経由でも end-to-end 完了** (設計書 §6.5 ゲート)
- 評価器 gate (`goal/lookup` or `goal/generator + verifier`) が AgentSquare 探索の **前段必須通過** として動作 (CLAUDE.md §9 と整合)
- 上流 AgentSquare の LLM 呼び出しを **`tsumiki.llm` 経由に書き換え** (CLAUDE.md §3 と整合)

### 0.2 位置づけ

Phase 7a〜7d で以下が確定:

- 7a: 統合方針 B-2 (modules/ + search/ + module_{evolution,recombination,predictor}/ のみ vendoring)
- 7b: パッケージ再構成, `policy/{compose,agentsquare}/` の骨組み配置済
- 7c: `examples/{nda,iso27001}/` リファレンス実装
- 7d: LLM プロバイダ層拡張, ただし **generator パスは下流契約不整合で 7d-4 失敗** (申し送り §8.2)

Phase 7e で AgentSquare 実装を取り込み, Phase 8 (Zenn Part 3/4 公開 + OSS リリース) の最低条件を満たす.

### 0.3 7d 申し送りの扱い (重要)

7d-4 観測で発覚した **generator 下流契約問題** (主 metric キー不一致, input_signature 自由化, typical_failure 意図反映不可) は Phase 7e と **論理的に独立** している:

- AgentSquare 統合: ポリシー層の合成・探索エンジン
- generator 改修: 評価器自動生成の契約強化

両者は並行可能だが, **本書は AgentSquare 統合のみを射程** とし, generator 改修は `phase7e_bonus_generator_fix_design.md` (Phase 7e 着手後または並行) として分離する.

理由:
- AgentSquare 統合は 3〜5 日, generator 改修は 1〜2 日と工数が違う
- 評価器 gate (Phase 7e) は **既存 seed 評価器** で動作確証できる (流用パスは Phase 5c/6 で実証済). generator パスは 7e の合格条件には含めない
- Phase 8 公開時に「generator は β 機能」と明示する戦略も取れる

## 1. AgentSquare 上流の構造再確認 (Phase 7a §3.1 より)

```
AgentSquare/ (upstream)
├── modules/
│   ├── memory_modules.py        # MemoryBase, MemoryDILU, MemoryGenerative ...
│   ├── planning_modules.py      # PlanningBase, PlanningIO, PlanningDILU ...
│   ├── reasoning_modules.py     # ReasoningBase, ReasoningCOT, ReasoningIO, ReasoningTOT ...
│   └── tooluse_modules.py       # ToolUseBase, ToolUseIO, ToolUseBench ...
├── module_evolution/
├── module_predictor/
├── module_recombination/
├── search/
└── tasks/                       # ALFWorld, WebShop, M3Tooleval, SciWorld (全捨て)
```

ライセンス: Apache-2.0 (Phase 7a §5.3 で確認, 既に LICENSE / NOTICE / THIRD_PARTY_LICENSES 配置済).

## 2. Vendoring 範囲と取り込み手順

### 2.1 取り込み対象と配置先

| 上流パス | 配置先 (tsumiki) | 改変内容 |
| --- | --- | --- |
| `modules/memory_modules.py` | `src/tsumiki/policy/agentsquare/memory.py` | OpenAI SDK 直接呼び出しを `tsumiki.llm` 経由に差し替え |
| `modules/planning_modules.py` | `src/tsumiki/policy/agentsquare/planning.py` | 同上 |
| `modules/reasoning_modules.py` | `src/tsumiki/policy/agentsquare/reasoning.py` | 同上 |
| `modules/tooluse_modules.py` | `src/tsumiki/policy/agentsquare/tooluse.py` | 同上 + `tsumiki.tools` プラグイン接続点 |
| `module_evolution/` | `src/tsumiki/policy/agentsquare/evolution/` | LLM 呼び出し差し替え, 評価器呼び出しを `eval/generated/` lookup に |
| `module_recombination/` | `src/tsumiki/policy/agentsquare/recombination/` | 同上 |
| `module_predictor/` | `src/tsumiki/policy/agentsquare/predictor/` | in-context surrogate の LLM 呼び出しを `tsumiki.llm` 経由 |
| `search/` | `src/tsumiki/policy/agentsquare/search/` | 同上, ベンチマーク統合は捨てる |

### 2.2 取り込みの段階

| 段階 | 内容 | 完了条件 |
| --- | --- | --- |
| 7e-1 | 上流 commit SHA を `docs/agentsquare_vendoring.md` に記録, modules/*.py を取り込み (LLM 呼び出しは未差し替え) | `import tsumiki.policy.agentsquare.{memory,planning,reasoning,tooluse}` が通る |
| 7e-2 | modules/*.py の LLM 呼び出しを `tsumiki.llm.client` 経由に書き換え | 4 ファイル + smoke test (mock client で chat が呼ばれることを確認) |
| 7e-3 | `module_evolution/`, `module_recombination/`, `module_predictor/`, `search/` を取り込み + LLM 差し替え | `import` 通過 + smoke |
| 7e-4 | `tsumiki.policy.compose` の薄いラッパを実装 | TaskSpec + 承認済み評価器 → モジュール探索起動 → 結果返却 |
| 7e-5 | 評価器 gate を `compose` 前段に強制 (CLAUDE.md §9) | gate 通過しないと探索が起動しないことを test で確認 |
| 7e-6 | `examples/{nda,iso27001}/run.sh` を `--use-compose` オプションで `policy.compose` 経由実行可能に | 両ドメインで end-to-end 完了 (試走) |
| 7e-7 | 結果報告書 `phase7e_compose_<date>.md` | §6 ゲート全充足判定 |

### 2.3 捨てるもの (Phase 7a §5.2 と一致)

- `tasks/alfworld/`, `tasks/webshop/`, `tasks/m3tooleval/`, `tasks/sciworld/` 全捨て
- 上流 `requirements.txt` の `alfworld`, `langchain*` 依存
- (上流の) README / video.mp4 / 学術ベンチ用スクリプト

### 2.4 vendoring commit SHA の記録

`docs/agentsquare_vendoring.md` を新規作成し以下を記録:

- 上流リポジトリ: https://github.com/tsinghua-fib-lab/AgentSquare
- 取り込み commit SHA (Phase 7e 着手時の上流 HEAD)
- 取り込んだファイル一覧
- 改変サマリ (LLM 呼び出し差し替え, タスクハードコード削除等)
- 上流追随ポリシー (Phase 7a §5.4: 四半期に 1 回確認)

## 3. LLM 呼び出し差し替え方針 (CLAUDE.md §3)

### 3.1 上流の典型パターン (推定)

```python
# 上流の典型
from openai import OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
resp = client.chat.completions.create(model="gpt-3.5-turbo", messages=[...])
```

### 3.2 取り込み後の形

```python
# tsumiki 側
from tsumiki.llm import LLMSettings, build_client
from tsumiki.data.synthesis import make_openai_chat_fn  # ChatFn ファクトリ

settings = LLMSettings.from_env()
client = build_client(settings)
chat_fn = make_openai_chat_fn(
    client,
    settings.model,
    temperature=settings.temperature,
    seed=42,
    num_ctx=8192 if settings.is_ollama else None,
)
response_text = chat_fn(prompt).content
```

または, モジュール初期化時に `chat_fn` を注入する DI パターン:

```python
class ReasoningCOT(ReasoningBase):
    def __init__(self, chat_fn: ChatFn, ...):
        self.chat_fn = chat_fn
```

DI 採用が筋. テスト時の mock 注入も容易.

### 3.3 上流の `gpt-3.5-turbo` ハードコード削除

上流の `--model gpt-3.5-turbo-0125` 等のハードコード文字列は **全て削除**. `settings.model` を渡す形に統一.

## 4. `tsumiki.policy.compose` 仕様

### 4.1 役割

「TaskSpec + 承認済み評価器 + Knowledge」から AgentSquare のモジュール探索を起動する **薄いラッパ**.

### 4.2 API (仮)

```python
# src/tsumiki/policy/compose/__init__.py

from dataclasses import dataclass
from tsumiki.goal.specs import TaskSpec, EvaluatorSpec
from tsumiki.knowledge.schemas.ng_patterns import NGPatternBook
from tsumiki.llm.client import LLMSettings


@dataclass(frozen=True)
class ComposeConfig:
    task_spec: TaskSpec
    evaluator_spec: EvaluatorSpec       # 承認済み (流用 or 生成 + verify 通過)
    knowledge: NGPatternBook
    llm_settings: LLMSettings
    max_search_depth: int = 3
    seed: int = 42


@dataclass(frozen=True)
class ComposeResult:
    selected_modules: dict[str, str]    # e.g. {"planning": "PlanningIO", "reasoning": "ReasoningCOT", ...}
    runtime_chat_fn: Any                # 探索で選ばれた構成での chat_fn
    search_score: float                 # 探索で得た最良スコア
    search_history: list[dict]          # MLflow 記録用


def run_compose(cfg: ComposeConfig) -> ComposeResult:
    """評価器 gate を通過した後, AgentSquare モジュール探索を起動する."""
    # 1. CLAUDE.md §9: 評価器が無い状態で自動探索を回さない
    _assert_evaluator_gate_passed(cfg.evaluator_spec)
    # 2. AgentSquare の探索エンジン起動
    from tsumiki.policy.agentsquare.search import run_search
    result = run_search(
        task_spec=cfg.task_spec,
        evaluator=cfg.evaluator_spec,
        knowledge=cfg.knowledge,
        llm_settings=cfg.llm_settings,
        ...
    )
    return ComposeResult(...)


def _assert_evaluator_gate_passed(evaluator_spec: EvaluatorSpec) -> None:
    """評価器が承認済 (lookup hit or verify 通過) であることを assert.
    CLAUDE.md §9: 評価器が無い状態で自動探索を回さない."""
    if not evaluator_spec.is_approved():
        raise RuntimeError(
            f"evaluator {evaluator_spec.id} is not approved; "
            "must pass goal/lookup or goal/verifier before compose"
        )
```

### 4.3 `is_approved()` の実装

既存 `EvaluatorSpec` に `approved_by` フィールドあり. `approved_by != ""` を `is_approved=True` の条件とする (Phase 5c で `auto` 設定済).

## 5. `runner/e2e.py` との接続

### 5.1 現状 (Phase 5c〜7d)

`run_e2e()` は以下の固定パイプラインを実行:

1. parser → TaskSpec
2. lookup (流用) or generator + verifier (新規生成) → EvaluatorSpec
3. knowledge ロード
4. synth (clean → synth NG sample)
5. variant=reuse + variant=zerobase 実行
6. paired_diff 算出

### 5.2 Phase 7e で追加 (オプトイン)

Phase 5c 互換動作を保ちつつ, `--use-compose` フラグで `policy.compose` 経由に切替:

```python
class E2EConfig:
    ...
    use_compose: bool = False           # Phase 7e で追加
    compose_max_depth: int = 3
```

`use_compose=True` 時のパイプライン:

1〜4. 同上
5. **`compose.run_compose(...)` 起動** → `selected_modules` + `runtime_chat_fn` を取得
6. `runtime_chat_fn` で variant=reuse + variant=zerobase 実行 (5c と同型)
7. paired_diff 算出 + `selected_modules` を MLflow に記録

Phase 5c 互換を破壊しない. デフォルト `use_compose=False`.

## 6. 主指標と合格条件 (実験前固定)

### 6.1 主指標

| 指標 | 用途 |
| --- | --- |
| `import tsumiki.policy.compose.run_compose` が通る | 7e-4 のコード骨格完成 |
| `_assert_evaluator_gate_passed` が未承認時に raise | 7e-5 評価器 gate 動作 |
| AgentSquare 探索が起動し `selected_modules` を返す | 7e-3 探索エンジン動作 |
| `examples/{nda,iso27001}/run.sh --use-compose` の paired_diff が Phase 5c/6 baseline と ±0.05 内 | 7e-6 同一フレーム下の挙動確証 |
| pytest 全体 PASS (Phase 7d 時点 201 件 + 7e 追加分) | リグレッションなし |

### 6.2 合格条件 (後出ししない)

| ゲート | 条件 |
| --- | --- |
| Vendoring 完了 | `src/tsumiki/policy/agentsquare/{memory,planning,reasoning,tooluse}.py` + `{evolution,recombination,predictor,search}/` が配置され import 通過 |
| LLM 差し替え | 取り込んだ全 .py 内で `from openai import OpenAI` が **0 件** (`tsumiki.llm` 経由のみ) |
| ライセンス遵守 | LICENSE / NOTICE / THIRD_PARTY_LICENSES/AgentSquare/LICENSE が揃い, 取り込み元コメント (Apache-2.0 derived from <SHA>) が各ファイル冒頭にある |
| 評価器 gate | `_assert_evaluator_gate_passed` が未承認 EvaluatorSpec で `RuntimeError` を raise (unit test) |
| `compose.run_compose` 動作 | mock chat_fn + seed 評価器で `ComposeResult` が返る (unit test) |
| **同一フレーム下の挙動** | `examples/{nda,iso27001}/run.sh --use-compose` で paired_diff が NDA +0.261 ±0.05 / ISO27001 +0.029 ±0.05 |
| リグレッション | pytest 全体 PASS, 既存 7d-3 の `LLMSettings` 動作変化なし |

### 6.3 「除外」する観点 (Phase 7-bonus / Phase 9+ に切り出し)

- generator 下流契約改修 (7d-4 申し送り) → `phase7e_bonus_generator_fix_design.md` で別立て
- `LLMSettings.from_env_with_overrides()` CLI 復活 → Phase 7-bonus
- AgentSquare 探索の hyperparameter 最適化 → Phase 9+
- 3 seed CI / 人手較正 → Phase 9+

## 7. 工数見積

| サブ | 内容 | 期間 |
| --- | --- | --- |
| 7e-1 | modules/*.py 取り込み (未改変) | 0.5 日 |
| 7e-2 | LLM 呼び出し差し替え (DI 化) + smoke | 1 日 |
| 7e-3 | module_{evolution,recombination,predictor}, search 取り込み + 差し替え + smoke | 1〜1.5 日 |
| 7e-4 | `tsumiki.policy.compose` 薄いラッパ実装 | 0.5 日 |
| 7e-5 | 評価器 gate 実装 + unit test | 0.5 日 |
| 7e-6 | `examples/*/run.sh --use-compose` + 試走 (両ドメイン) | 1 日 + ollama or Azure 試走 2-4 時間 |
| 7e-7 | 結果報告書 | 0.5 日 |
| 合計 | | **約 5〜6 日 + 試走** |

## 8. 実行手順と再現コマンド (雛形)

### 8.1 7e-1: 上流取り込み

```bash
# 上流 HEAD を確認
git ls-remote https://github.com/tsinghua-fib-lab/AgentSquare HEAD

# tmp に clone
git clone --depth 1 https://github.com/tsinghua-fib-lab/AgentSquare /tmp/agentsquare_upstream

# commit SHA を記録
cd /tmp/agentsquare_upstream && git log -1 --format="%H %s" > /tmp/asq_sha.txt
cat /tmp/asq_sha.txt
# 例: a1b2c3... Update README

# 4 ファイル取り込み
cp /tmp/agentsquare_upstream/modules/{memory,planning,reasoning,tooluse}_modules.py \
   src/tsumiki/policy/agentsquare/

# リネーム
mv src/tsumiki/policy/agentsquare/memory_modules.py src/tsumiki/policy/agentsquare/memory.py
mv src/tsumiki/policy/agentsquare/planning_modules.py src/tsumiki/policy/agentsquare/planning.py
mv src/tsumiki/policy/agentsquare/reasoning_modules.py src/tsumiki/policy/agentsquare/reasoning.py
mv src/tsumiki/policy/agentsquare/tooluse_modules.py src/tsumiki/policy/agentsquare/tooluse.py

# 上流 LICENSE を取得
curl -sS https://raw.githubusercontent.com/tsinghua-fib-lab/AgentSquare/<SHA>/LICENSE \
  -o THIRD_PARTY_LICENSES/AgentSquare/LICENSE
```

### 8.2 7e-2: LLM 差し替え (各ファイルの先頭にヘッダを追加)

```python
# src/tsumiki/policy/agentsquare/planning.py の冒頭
"""tsumiki: AgentSquare planning モジュール (vendored, Apache-2.0).

Upstream: https://github.com/tsinghua-fib-lab/AgentSquare/blob/<SHA>/modules/planning_modules.py
Vendored at Phase 7e (2026-06-19), see docs/agentsquare_vendoring.md.

Modifications:
- OpenAI SDK 直接呼び出しを ChatFn 注入 (tsumiki.llm 経由) に書き換え
- gpt-3.5-turbo ハードコードを settings.model に変更
- alfworld 依存を削除
"""
```

### 8.3 7e-6: 試走

```bash
# 環境変数は Phase 7d と同じ (Azure か ollama)
bash examples/nda/run.sh --use-compose
bash examples/iso27001/run.sh --use-compose
```

`--use-compose` は `run_phase5c_dryrun.py` の新規 CLI 引数として実装 (`E2EConfig.use_compose=True` を渡す).

## 9. リスクと対応

| リスク | 対応 |
| --- | --- |
| 上流 4 ファイルが LangChain 依存 | LangChain 呼び出し部分も `tsumiki.llm` に置換. 不可能なら該当バリアント (`MemoryGenerative` 等) を取り込み対象から除外し 7e 報告書に明記 |
| `module_evolution/` のロジックが alfworld 依存 | 該当部分を切り出して `# pragma: tsumiki-skip` でコメントアウト, 7e 報告書に明記 |
| 試走時間が想定超過 | 7e-6 試走は seed 1 件 + n_synth_per_pattern=1 で smoke 走行を許容. paired_diff の精度が落ちる場合は「smoke のみ実走」と明示 |
| LICENSE / NOTICE 漏れ | ruff の自作ルール or 簡易 grep test で `Apache-2.0 derived` が各 vendored ファイルに含まれることを確認 |
| AgentSquare 上流の更新 | 上流追随は Phase 8 公開後の四半期 1 回ペースで実施 (Phase 7a §5.4 で確定) |
| compose ラッパが Phase 5c/6 baseline と差分を出す | これは想定外. 出た場合は AgentSquare 探索のシード固定漏れ等を疑う. 7e 報告書で原因分析 |
| `is_approved()` 実装が既存 EvaluatorSpec と衝突 | `approved_by != ""` を判定子に. Phase 5c で `auto` 設定済のため衝突なし |

## 10. Phase 7d 申し送りの位置づけ

7d-4 観測の §8.2 (generator 改修) は **Phase 7e の射程外**. ただし以下の手当を 7e で同時実施:

- `compose.run_compose` 前段の `_assert_evaluator_gate_passed` は CLAUDE.md §9 の体現で, generator 改修なしでも seed 評価器 (Phase 5c/6 流用) で動作する
- generator 改修 (Phase 7-bonus) は AgentSquare 統合と独立に進められる
- Phase 8 (公開) では「generator は β 機能, 流用パスが主」と README に明記する戦略

## 11. Phase 7-bonus / Phase 8 への申し送り

Phase 7e 完了後:

| タスク | 内容 | 工数目安 |
| --- | --- | --- |
| Phase 7-bonus-1 | generator 主 metric 整合制約 (`modification_success_rate` 必須化 + Summary false OK 警告) | 1 日 |
| Phase 7-bonus-2 | input_signature の schemas/ 固定 (parser 制約) | 0.5 日 |
| Phase 7-bonus-3 | `LLMSettings.from_env_with_overrides()` CLI 復活 (ユーザー要望) | 0.5 日 |
| Phase 8 | Zenn Part 3 / 4 公開 + GitHub リポジトリ公開 (README, CONTRIBUTING, LICENSE 整備) | 2 週 |

Phase 7-bonus 3 件は Phase 7e と並行 or 7e 完了後に着手. Phase 8 は 7-bonus 完了後.

## 12. 関連

| 項目 | パス |
| --- | --- |
| 設計 (本書) | `docs/experiments/phase7e_design.md` |
| 結果報告 | `docs/experiments/phase7e_compose_<date>.md` (実行後作成) |
| Phase 7 設計 | [`phase7_design.md`](phase7_design.md) §1 (7e) / §2 / §6.5 |
| Phase 7a 結果 | [`phase7a_agentsquare_2026-06-19.md`](phase7a_agentsquare_2026-06-19.md) |
| Phase 7b 結果 | [`phase7b_packaging_2026-06-19.md`](phase7b_packaging_2026-06-19.md) |
| Phase 7c 結果 | [`phase7c_examples_2026-06-19.md`](phase7c_examples_2026-06-19.md) |
| Phase 7d 結果 | [`phase7d_provider_and_generator_2026-06-19.md`](phase7d_provider_and_generator_2026-06-19.md) §8.2 申し送り |
| 計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) §10.4 |
| 上流 | https://github.com/tsinghua-fib-lab/AgentSquare |
| Vendoring 記録 | `docs/agentsquare_vendoring.md` (Phase 7e 着手時に新規作成) |
