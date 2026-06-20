"""tsumiki: AgentSquare module evolution (vendored from Apache-2.0).

Upstream: https://github.com/tsinghua-fib-lab/AgentSquare/blob/8f5b3fe5d8a32f9b59d20370823bef2a2c86928c/search/module_evolution.py
Vendored at Phase 7e-3 (2026-06-19), rewritten at Phase 7e-3.
See docs/agentsquare_vendoring.md for vendoring policy.

Phase 7e-3 modifications:
- `from openai import OpenAI` を削除. `JsonChatFn` (DI) を `evolve()` に受け取る形に変更.
- `backoff` 依存を削除. リトライは tsumiki 側の `llm/client.py` 経路で吸収する想定.
- `__main__` ブロックを削除 (CLI は tsumiki 側で `experiments/` 経由).
- `with open('output_*.jsonl', 'a')` のファイル書き出しを `output_dir: Path | None` 引数化.
  `None` の場合は書き出さない.
- 上流の `get_prompt_X(modules, last_feedback)` 呼び出しは prompts 側の互換シグネチャ
  (last_feedback=None) で受ける.
- 上流の `feedback` keys 取り出しは保持. 上流 archive エントリに `feedback` が無いケースを
  想定して `.get('feedback', '')` を使用.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tsumiki.policy.agentsquare.evolution.prompts import (
    get_prompt_memory,
    get_prompt_planning,
    get_prompt_reasoning,
    get_prompt_tooluse,
)

# JsonChatFn: messages -> JSON object 形式の応答を返す ChatFn 変種.
# tsumiki 側で `response_format={"type": "json_object"}` を発行する OpenAI 互換クライアントを
# ラップして dict を返す関数を作る (詳細は `tsumiki.llm` 拡張で対応).
JsonChatFn = Callable[[list[dict[str, str]]], dict[str, Any]]


REQUIRED_KEYS = ["name", "thought", "module type", "code"]


def _ensure_keys_exist(response: dict[str, Any], keys: list[str]) -> bool:
    return all(key in response for key in keys)


def _solve_with_keys(
    chat_fn: JsonChatFn, msg_list: list[dict[str, str]], max_retries: int = 5
) -> dict[str, Any]:
    """Required keys を満たすまで chat_fn を呼ぶ (上流の while ループ相当, 上限付き)."""
    for _ in range(max_retries):
        response = chat_fn(msg_list)
        if _ensure_keys_exist(response, REQUIRED_KEYS):
            return response
    # 最後の応答をそのまま返す (上流挙動と一致, 後段で fallback)
    return response


def _fix_code_escapes(solution: dict[str, Any]) -> dict[str, Any]:
    if "code" in solution and isinstance(solution["code"], str):
        solution["code"] = (
            solution["code"].replace("'\n'", "'\\n'").replace(":\n'", ":\\n'")
        )
    return solution


def _filter_archive(archive: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    """name='None' を除外, feedback 最終値を抽出する (上流 search/module_evolution.py と同型)."""
    modules: list[dict[str, Any]] = []
    last_feedback: str | None = None
    for item in archive:
        if str(item.get("name", "")).lower() == "none":
            continue
        item_copy = {k: v for k, v in item.items() if k != "feedback"}
        modules.append(item_copy)
        fb = item.get("feedback", "")
        if fb:
            last_feedback = fb
    return modules, last_feedback


def evolve(
    current_agent: dict[str, str],
    planning_archive: list[dict[str, Any]],
    reasoning_archive: list[dict[str, Any]],
    tooluse_archive: list[dict[str, Any]],
    memory_archive: list[dict[str, Any]],
    json_chat_fn: JsonChatFn,
    output_dir: Path | None = None,
) -> tuple[
    list[dict[str, str]],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """4 モジュール (planning/reasoning/memory/tooluse) に対し新規候補を 1 つずつ生成し,
    現 agent の各モジュールを差し替えた 4 つの新 agent を返す (上流挙動と同型).

    Args:
        current_agent: {'planning', 'reasoning', 'tooluse', 'memory'} の dict.
        *_archive: 各モジュール種別の archive.
        json_chat_fn: messages (system + user) -> dict を返す ChatFn 変種.
            tsumiki 側で OpenAI 互換クライアントを JSON mode でラップする.
        output_dir: jsonl 出力先 (任意). None の場合は書き出さない.

    Returns:
        (evolution_agents, planning, reasoning, memory, tooluse) の tuple.
        各 module の dict は失敗時 `{}` を返す.
    """
    planning_modules, planning_last_feedback = _filter_archive(planning_archive)
    memory_modules, memory_last_feedback = _filter_archive(memory_archive)
    tooluse_modules, tooluse_last_feedback = _filter_archive(tooluse_archive)
    reasoning_modules, reasoning_last_feedback = _filter_archive(reasoning_archive)

    sys_prompt, prompt = get_prompt_reasoning(reasoning_modules, reasoning_last_feedback)
    msg_list_reasoning = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt},
    ]
    sys_prompt, prompt = get_prompt_planning(planning_modules, planning_last_feedback)
    msg_list_planning = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt},
    ]
    sys_prompt, prompt = get_prompt_memory(memory_modules, memory_last_feedback)
    msg_list_memory = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt},
    ]
    sys_prompt, prompt = get_prompt_tooluse(tooluse_modules, tooluse_last_feedback)
    msg_list_tooluse = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt},
    ]

    evolution_agents: list[dict[str, str]] = []
    next_reasoning: dict[str, Any] = {}
    next_planning: dict[str, Any] = {}
    next_memory: dict[str, Any] = {}
    next_tooluse: dict[str, Any] = {}

    try:
        next_reasoning = _fix_code_escapes(_solve_with_keys(json_chat_fn, msg_list_reasoning))
        next_planning = _fix_code_escapes(_solve_with_keys(json_chat_fn, msg_list_planning))
        next_memory = _fix_code_escapes(_solve_with_keys(json_chat_fn, msg_list_memory))
        next_tooluse = _fix_code_escapes(_solve_with_keys(json_chat_fn, msg_list_tooluse))

        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            for name, sol in [
                ("output_reasoning.jsonl", next_reasoning),
                ("output_planning.jsonl", next_planning),
                ("output_memory.jsonl", next_memory),
                ("output_tooluse.jsonl", next_tooluse),
            ]:
                with (output_dir / name).open("a", encoding="utf-8") as f:
                    f.write(json.dumps(sol) + "\n")

        evolution_agents.extend(
            [
                {
                    "planning": next_planning.get("name", current_agent["planning"]),
                    "reasoning": current_agent["reasoning"],
                    "tooluse": current_agent["tooluse"],
                    "memory": current_agent["memory"],
                },
                {
                    "planning": current_agent["planning"],
                    "reasoning": next_reasoning.get("name", current_agent["reasoning"]),
                    "tooluse": current_agent["tooluse"],
                    "memory": current_agent["memory"],
                },
                {
                    "planning": current_agent["planning"],
                    "reasoning": current_agent["reasoning"],
                    "tooluse": next_tooluse.get("name", current_agent["tooluse"]),
                    "memory": current_agent["memory"],
                },
                {
                    "planning": current_agent["planning"],
                    "reasoning": current_agent["reasoning"],
                    "tooluse": current_agent["tooluse"],
                    "memory": next_memory.get("name", current_agent["memory"]),
                },
            ]
        )
    except Exception as e:  # noqa: BLE001
        print(f"[tsumiki.evolve] error: {e}")

    return evolution_agents, next_planning, next_reasoning, next_memory, next_tooluse
