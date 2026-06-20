"""AgentSquare module evolution (vendored from Apache-2.0).

Phase 7e-3 (2026-06-19) で取り込み. 上流の `module_evolution/` と `search/module_evolution.py`
の混合をベースに, ChatFn DI 化 + JSON mode 用 chat fn 分離 + alfworld 固有 CLI 削除.

Public API:
- `evolve(current_agent, *_archive, json_chat_fn, output_dir=None) -> tuple`
- prompts: `get_init_archive_X()`, `get_prompt_X(archive, last_feedback=None)` (4 種)
"""

from tsumiki.policy.agentsquare.evolution.evolve import JsonChatFn, evolve
from tsumiki.policy.agentsquare.evolution.prompts import (
    get_init_archive_memory,
    get_init_archive_planning,
    get_init_archive_reasoning,
    get_init_archive_tooluse,
    get_prompt_memory,
    get_prompt_planning,
    get_prompt_reasoning,
    get_prompt_tooluse,
)

__all__ = [
    "JsonChatFn",
    "evolve",
    "get_init_archive_memory",
    "get_init_archive_planning",
    "get_init_archive_reasoning",
    "get_init_archive_tooluse",
    "get_prompt_memory",
    "get_prompt_planning",
    "get_prompt_reasoning",
    "get_prompt_tooluse",
]
