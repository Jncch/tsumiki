"""tsumiki: AgentSquare module recombination (vendored from Apache-2.0).

Upstream: https://github.com/tsinghua-fib-lab/AgentSquare/blob/8f5b3fe5d8a32f9b59d20370823bef2a2c86928c/search/recombination.py
Vendored at Phase 7e-3 (2026-06-19), rewritten at Phase 7e-3.

Phase 7e-3 modifications:
- `from utils import llm_response` を削除. ChatFn DI を `recombine()` に受け取る.
- `eval(response)` を `ast.literal_eval(response)` に変更 (任意コード実行回避).
- `model = 'gpt-4o-mini'` ハードコードを削除 (chat_fn 内で settings.model 完結).
- 上流の `module_recombination/module_recombination.py` (トップレベル副作用付き) は採用せず,
  関数化版 (`search/recombination.py`) を採用.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable

ChatFn = Callable[[str], str]


def _parse_agent_dict(response: str) -> dict[str, str]:
    """LLM 応答から {'planning':..., 'reasoning':..., 'tooluse':..., 'memory':...} 形式の
    dict を抽出する. literal_eval で失敗した場合は最初の {...} ブロックを抜き出して再試行.
    """
    try:
        return ast.literal_eval(response)
    except (ValueError, SyntaxError):
        pass
    match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
    if match:
        try:
            return ast.literal_eval(match.group(0))
        except (ValueError, SyntaxError):
            pass
    return {}


def recombine(
    task_description: str,
    current_agent: dict[str, str],
    planning_candidate: dict[str, str],
    reasoning_candidate: dict[str, str],
    tooluse_candidate: dict[str, str],
    memory_candidate: dict[str, str],
    tested_case: list[dict[str, object]],
    chat_fn: ChatFn,
) -> list[dict[str, str]]:
    """4 モジュール候補リストから新規 module 組み合わせを 1 つ LLM 提案させ,
    `current_agent` の各モジュールを差し替えた 4 つの新 agent を返す.

    Args:
        task_description: tsumiki 側でドメイン記述を渡す (上流は alfworld 固定).
        current_agent: {'planning', 'reasoning', 'tooluse', 'memory'} の dict.
        *_candidate: 各モジュール種別の {name: description} 辞書.
        tested_case: 既存組み合わせと performance の履歴.
        chat_fn: prompt -> text 形式の ChatFn.

    Returns:
        4 つの新 agent dict のリスト (各 1 module 差し替え).
    """
    prompt = (
        "You are an AI agent expert. Now you are required to design a LLM-based agent "
        "to solve the task of "
        + task_description
        + "The agent is composed of four fundamental modules(including None): "
        "planning, reasoning, tool use and memory. "
        "For each module you are required to choose one from the follwing provided candidates. "
        "Planning module candidates and descriptions: "
        + str(planning_candidate)
        + " Reasoning module candidates and descriptions: "
        + str(reasoning_candidate)
        + " Tool use module candidates and descriptions: "
        + str(tooluse_candidate)
        + " Memory module candidates and descriptions: "
        + str(memory_candidate)
        + "The performance of some existing module combinations: "
        + str(tested_case)
        + ". You are expected to give a new module combination to improve the performance "
        "on the task by considering (1) the matching degree between the module description "
        "and task description (2) performance of existing module combinations on the task. "
        "Your answer must follow the format and not contain any other information.:"
        + str(
            {
                "planning": "<your choice>",
                "reasoning": "<your choice>",
                "tooluse": "<your choice>",
                "memory": "<your choice>",
            }
        )
    )

    response = chat_fn(prompt)
    agent = _parse_agent_dict(response)

    planning = agent.get("planning", current_agent["planning"])
    reasoning = agent.get("reasoning", current_agent["reasoning"])
    tooluse = agent.get("tooluse", current_agent["tooluse"])
    memory = agent.get("memory", current_agent["memory"])

    return [
        {
            "planning": planning,
            "reasoning": current_agent["reasoning"],
            "tooluse": current_agent["tooluse"],
            "memory": current_agent["memory"],
        },
        {
            "planning": current_agent["planning"],
            "reasoning": reasoning,
            "tooluse": current_agent["tooluse"],
            "memory": current_agent["memory"],
        },
        {
            "planning": current_agent["planning"],
            "reasoning": current_agent["reasoning"],
            "tooluse": tooluse,
            "memory": current_agent["memory"],
        },
        {
            "planning": current_agent["planning"],
            "reasoning": current_agent["reasoning"],
            "tooluse": current_agent["tooluse"],
            "memory": memory,
        },
    ]
