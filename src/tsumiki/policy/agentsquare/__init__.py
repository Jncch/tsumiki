"""AgentSquare partial vendoring (Phase 7a §5 採用方針 B-2).

Phase 7e-1 (2026-06-19): 上流 `modules/{memory,planning,reasoning,tooluse}_modules.py`
を取り込み.
Phase 7e-2 (2026-06-19): LLM 呼び出しを `tsumiki.llm` 経由 ChatFn (DI) に書き換え,
langchain 依存を削除, タスク固有 import を tsumiki 側代替に置換, import smoke 通過.
Phase 7e-3 (2026-06-19): `module_evolution/`, `module_recombination/`, `module_predictor/`,
`search/` を取り込み. ChatFn DI 化 + alfworld 固有ベンチマーク削除 + benchmark_fn DI 化.

詳細: `docs/agentsquare_vendoring.md` および
`docs/experiments/phase7e{1,2,3}_*_2026-06-19.md`.

上流ライセンス: Apache-2.0 (`THIRD_PARTY_LICENSES/AgentSquare/LICENSE`).
"""

from tsumiki.policy.agentsquare import (
    evolution,
    memory,
    planning,
    predictor,
    reasoning,
    recombination,
    search,
    tooluse,
)

__all__ = [
    "evolution",
    "memory",
    "planning",
    "predictor",
    "reasoning",
    "recombination",
    "search",
    "tooluse",
]
