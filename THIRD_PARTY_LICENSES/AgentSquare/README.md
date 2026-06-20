# AgentSquare (vendored portions)

This directory holds the upstream LICENSE and attribution for code
vendored from AgentSquare (https://github.com/tsinghua-fib-lab/AgentSquare).

## LICENSE file

The `LICENSE` file in this directory is the Apache License 2.0 text obtained
from the Apache Foundation (`https://www.apache.org/licenses/LICENSE-2.0.txt`).
Upstream AgentSquare declares Apache-2.0 in its README but does not ship the
full license text in its repository top, so tsumiki places the canonical
Apache-2.0 text here for downstream consumers.

Upstream commit SHA, vendoring scope, and modifications are recorded in
[`../../docs/agentsquare_vendoring.md`](../../docs/agentsquare_vendoring.md).

## Vendoring scope (current at Phase 7e-1, 2026-06-19)

Vendored (Phase 7e-1):

- `modules/memory_modules.py` → `src/tsumiki/policy/agentsquare/memory.py`
- `modules/planning_modules.py` → `src/tsumiki/policy/agentsquare/planning.py`
- `modules/reasoning_modules.py` → `src/tsumiki/policy/agentsquare/reasoning.py`
- `modules/tooluse_modules.py` → `src/tsumiki/policy/agentsquare/tooluse.py`

Planned for Phase 7e-3:

- `module_evolution/`, `module_recombination/`, `module_predictor/`, `search/`

Excluded (per Phase 7a §5.2):

- `tasks/{alfworld,webshop,m3tooleval,sciworld}/`
- `requirements.txt` entries for `alfworld`, `langchain*`
- Task-specific helpers (`tasks/*/utils.py`, `planning_prompt.py`, `tooluse_IO_pool.py`)
- video.mp4 and other LFS binaries

All LLM call sites will be rewritten to go through `src/tsumiki/llm/`
(CLAUDE.md §3) at Phase 7e-2.
