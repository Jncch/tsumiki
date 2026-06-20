"""AgentSquare module recombination (vendored from Apache-2.0).

Phase 7e-3 (2026-06-19) で取り込み. 上流の `search/recombination.py` をベースに,
ChatFn DI 化 + `eval()` を `ast.literal_eval()` に置換 + model ハードコード削除.
"""

from tsumiki.policy.agentsquare.recombination.recombine import ChatFn, recombine

__all__ = ["ChatFn", "recombine"]
