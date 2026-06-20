"""AgentSquare agent search loop (vendored from Apache-2.0).

Phase 7e-3 (2026-06-19) で取り込み. 上流の `search/agent_search.py` をベースに,
alfworld 固有ベンチマーク (`run_benchmark`, `write_test_module`, etc.) を **削除**し,
`benchmark_fn: Callable[[Agent], float]` を DI で受け取る形に書き換え.

archives/ 配下に上流の `{memory,planning,reasoning,tooluse}_modules.json` を同梱.

Public API:
- `run_search(benchmark_fn, chat_fn, json_chat_fn, task_description, ...) -> dict`
- `load_default_archives() -> (candidates, archives)`
- `load_modules_from_json(filename) -> (candidates, archive)`
"""

from tsumiki.policy.agentsquare.search.loop import (
    ARCHIVE_DIR,
    MODULE_TYPES,
    Agent,
    BenchmarkFn,
    ChatFn,
    TestedCase,
    load_default_archives,
    load_modules_from_json,
    run_search,
)

__all__ = [
    "ARCHIVE_DIR",
    "MODULE_TYPES",
    "Agent",
    "BenchmarkFn",
    "ChatFn",
    "TestedCase",
    "load_default_archives",
    "load_modules_from_json",
    "run_search",
]
