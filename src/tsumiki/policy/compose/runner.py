"""`run_compose`: TaskSpec + 承認済み評価器から AgentSquare 探索を起動する薄いラッパ.

Phase 7e-4 (2026-06-19) で追加. 設計書 `phase7e_design.md` §4.

CLAUDE.md §9 (評価器が無い状態で自動探索を回さない) を体現するため,
`_assert_evaluator_gate_passed` で `approved_by != ""` を検査する.
"""

from __future__ import annotations

from tsumiki.goal.specs import EvaluatorSpec
from tsumiki.policy.agentsquare.search import run_search
from tsumiki.policy.compose.config import ComposeConfig, ComposeResult


def _assert_evaluator_gate_passed(evaluator_spec: EvaluatorSpec) -> None:
    """評価器が承認済 (lookup hit or verify 通過) であることを assert する.

    CLAUDE.md §9: 評価器が無い状態で自動探索を回さない.
    設計書 §4.3: `EvaluatorSpec.is_approved()` (= `approved_by != ""`) を判定子.
    """
    if not evaluator_spec.is_approved():
        raise RuntimeError(
            f"evaluator {evaluator_spec.id!r} is not approved "
            f"(approved_by is empty); must pass goal/lookup or "
            f"goal/verifier before compose"
        )


def run_compose(cfg: ComposeConfig) -> ComposeResult:
    """評価器 gate を通過した後, AgentSquare モジュール探索を起動する.

    1. CLAUDE.md §9: 評価器 gate 強制 (`_assert_evaluator_gate_passed`).
    2. AgentSquare 探索 (`run_search`) を `benchmark_fn` DI で起動.
    3. 結果を `ComposeResult` に詰めて返す.

    Raises:
        RuntimeError: 評価器が未承認 (`approved_by` 空) の場合.
    """
    _assert_evaluator_gate_passed(cfg.evaluator_spec)

    # 上流 task_description は alfworld ハードコードだったため
    # tsumiki 側ではドメイン記述として TaskSpec.raw_goal を流用.
    # Phase 7e-6 以降で domain 別 archive と組み合わせて精度向上を見込む.
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
