"""AgentSquare evolution prompts (vendored from Apache-2.0).

各 prompts ファイルは `get_init_archive_X()` と `get_prompt_X(archive, last_feedback=None)`
を提供する. 本体は alfworld 固有の長大な英語プロンプト + サンプル code 文字列.

7e-3 では prompts のシグネチャを呼び出し側 (search/module_evolution.py) と互換にするため
`last_feedback` 引数を追加した (本実装では未使用).

詳細: docs/agentsquare_vendoring.md, docs/experiments/phase7e3_search_2026-06-19.md.
"""

from tsumiki.policy.agentsquare.evolution.prompts.memory import (
    get_init_archive_memory,
    get_prompt_memory,
)
from tsumiki.policy.agentsquare.evolution.prompts.planning import (
    get_init_archive_planning,
    get_prompt_planning,
)
from tsumiki.policy.agentsquare.evolution.prompts.reasoning import (
    get_init_archive_reasoning,
    get_prompt_reasoning,
)
from tsumiki.policy.agentsquare.evolution.prompts.tooluse import (
    get_init_archive_tooluse,
    get_prompt_tooluse,
)

__all__ = [
    "get_init_archive_memory",
    "get_init_archive_planning",
    "get_init_archive_reasoning",
    "get_init_archive_tooluse",
    "get_prompt_memory",
    "get_prompt_planning",
    "get_prompt_reasoning",
    "get_prompt_tooluse",
]
