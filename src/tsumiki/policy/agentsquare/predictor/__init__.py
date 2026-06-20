"""AgentSquare module performance predictor (vendored from Apache-2.0).

Phase 7e-3 (2026-06-19) で取り込み. 上流の `search/module_predictor.py` をベースに,
ChatFn DI 化 + alfworld 固有 wildcard import 削除 + golden_cases を引数化.
"""

from tsumiki.policy.agentsquare.predictor.predictor import (
    ChatFn,
    ModuleInfo,
    predict_performance,
)

__all__ = ["ChatFn", "ModuleInfo", "predict_performance"]
