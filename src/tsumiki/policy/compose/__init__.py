"""制約付き役割合成 (AgentSquare モジュール探索ラッパ).

Phase 7b で骨組のみ. Phase 7e-4 (2026-06-19) で `policy.agentsquare` の
vendored コードを呼び出す薄いラッパを実装.

評価器の lookup / generator 通過を gate として強制する (CLAUDE.md §9).

Public API:
- `ComposeConfig`, `ComposeResult` (frozen dataclass)
- `run_compose(cfg) -> ComposeResult`
- `_assert_evaluator_gate_passed(evaluator_spec)` (内部用, test 対象)
"""

from tsumiki.policy.compose.config import (
    BenchmarkFn,
    ChatFn,
    ComposeConfig,
    ComposeResult,
    JsonChatFn,
)
from tsumiki.policy.compose.runner import (
    _assert_evaluator_gate_passed,
    run_compose,
)

__all__ = [
    "BenchmarkFn",
    "ChatFn",
    "ComposeConfig",
    "ComposeResult",
    "JsonChatFn",
    "_assert_evaluator_gate_passed",
    "run_compose",
]
