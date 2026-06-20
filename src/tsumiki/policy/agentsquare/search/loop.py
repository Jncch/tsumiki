"""tsumiki: AgentSquare agent search loop (vendored from Apache-2.0).

Upstream: https://github.com/tsinghua-fib-lab/AgentSquare/blob/8f5b3fe5d8a32f9b59d20370823bef2a2c86928c/search/agent_search.py
Vendored at Phase 7e-3 (2026-06-19), rewritten at Phase 7e-3.

Phase 7e-3 modifications:
- alfworld 固有のベンチマーク実行 (`run_benchmark`, `write_test_module`, `cleanup_test_modules`,
  `prepare_test_agent`, `test_new_modules`, `test_agent`) を **削除**.
  tsumiki 側ではドメイン非依存に `benchmark_fn: Callable[[Agent], float]` を DI で受け取り,
  agent の performance を測る形に統一する.
- `agent_search()` を `run_search(benchmark_fn, ..., ...)` に書き換え.
- `concurrent.futures.ProcessPoolExecutor` を削除 (alfworld 並列実行に依存).
  tsumiki 側で並列が必要なら呼び出し側で `benchmark_fn` をプロセスプール化する想定.
- `load_modules_from_json` を保持. archives JSON は `archives/` に同梱.
- `save_to_json` のロギングを `output_dir: Path | None` 引数化 (None で書き出し抑制).
- `__main__` ブロックを削除.
- `evolution()` / `recombination()` / `predict_performance()` は tsumiki 側の関数を import.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

from tsumiki.policy.agentsquare.evolution import (
    JsonChatFn,
    evolve,
)
from tsumiki.policy.agentsquare.predictor import ModuleInfo, predict_performance
from tsumiki.policy.agentsquare.recombination import recombine

ChatFn = Callable[[str], str]
BenchmarkFn = Callable[[dict[str, str]], float]

MODULE_TYPES = ("planning", "reasoning", "tooluse", "memory")

ARCHIVE_DIR = Path(__file__).parent / "archives"


class Agent(TypedDict):
    planning: str
    reasoning: str
    tooluse: str
    memory: str


class TestedCase(Agent):
    performance: float


def load_modules_from_json(
    filename: str | Path,
) -> tuple[dict[str, str], list[ModuleInfo]]:
    """Module 情報の JSON ファイルから candidates と archive を読み込む."""
    path = Path(filename)
    if not path.is_absolute() and not path.exists():
        candidate = ARCHIVE_DIR / path.name
        if candidate.exists():
            path = candidate
    with path.open("r", encoding="utf-8") as f:
        modules = json.load(f)
    candidates = {module["name"]: module["thought"] for module in modules}
    archive: list[ModuleInfo] = [
        {
            "thought": module["thought"],
            "name": module["name"],
            "module_type": module["module type"],
            "code": module["code"],
            "performance": module["performance"],
        }
        for module in modules
    ]
    return candidates, archive


def load_default_archives() -> tuple[dict[str, dict[str, str]], dict[str, list[ModuleInfo]]]:
    """同梱の archives/*.json (4 種) を読み込んで返す."""
    candidates: dict[str, dict[str, str]] = {}
    archives: dict[str, list[ModuleInfo]] = {}
    for module_type in MODULE_TYPES:
        cands, arch = load_modules_from_json(ARCHIVE_DIR / f"{module_type}_modules.json")
        candidates[module_type] = cands
        archives[module_type] = arch
    return candidates, archives


def _save_json(data: Any, filename: str, output_dir: Path | None) -> None:
    if output_dir is None:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / filename).open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def run_search(
    benchmark_fn: BenchmarkFn,
    chat_fn: ChatFn,
    json_chat_fn: JsonChatFn,
    task_description: str,
    candidates: dict[str, dict[str, str]] | None = None,
    archives: dict[str, list[ModuleInfo]] | None = None,
    initial_agent: Agent | None = None,
    initial_performance: float = 0.0,
    num_iterations: int = 10,
    output_dir: Path | None = None,
    golden_cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """AgentSquare 探索ループ.

    Args:
        benchmark_fn: Agent dict -> performance float を返す評価器 (tsumiki 側で実装).
        chat_fn: recombination 用 ChatFn.
        json_chat_fn: evolution 用 JSON 応答 ChatFn.
        task_description: ドメイン記述 (上流の alfworld ハードコードを引数化).
        candidates / archives: 省略時は同梱の archives/*.json を使う.
        initial_agent: 探索開始 agent (省略時は 'None'/'IO'/'None'/'None').
        initial_performance: 開始 performance (省略時は 0.0).
        num_iterations: 探索イテレーション数.
        output_dir: 中間ファイル出力先 (任意).
        golden_cases: predictor 用既知 (agent, performance) ペア.

    Returns:
        dict with keys: best_agent, best_performance, tested_cases, test_counts,
            best_performances, agent_counts.
    """
    if candidates is None or archives is None:
        candidates, archives = load_default_archives()

    current_agent: Agent = initial_agent or {
        "planning": "None",
        "reasoning": "IO",
        "tooluse": "None",
        "memory": "None",
    }
    tested_cases: list[TestedCase] = [{**current_agent, "performance": initial_performance}]
    current_performance = initial_performance

    best_performances: list[float] = [current_performance]
    agent_counts: list[int] = [1]
    test_counts = {"total": 0, "iterations": []}

    for iteration in range(num_iterations):
        iter_test_count = 0

        # 1. Evolution
        evolution_results = evolve(
            current_agent,
            archives["planning"],
            archives["reasoning"],
            archives["tooluse"],
            archives["memory"],
            json_chat_fn=json_chat_fn,
            output_dir=output_dir,
        )
        evolution_agents = evolution_results[0]
        evolution_modules = {
            "planning": evolution_results[1],
            "reasoning": evolution_results[2],
            "memory": evolution_results[3],
            "tooluse": evolution_results[4],
        }

        # 2. Evolved agent 評価 (上流の test_new_modules / write_test_module を簡略化:
        #    tsumiki では evolution で生成された新モジュール code を archive に追加してから
        #    benchmark_fn に直接渡す形. benchmark_fn 側で agent dict を解釈する責任).
        for module_type, module_info in evolution_modules.items():
            name = module_info.get("name")
            if name and module_info.get("code"):
                candidates[module_type][name] = module_info.get("thought", "")
                archives[module_type].append(
                    {
                        "thought": module_info.get("thought", ""),
                        "name": name,
                        "module_type": module_type,
                        "code": module_info.get("code", ""),
                        "performance": 0.0,
                    }
                )

        for agent in evolution_agents:
            if agent["tooluse"] != "None":
                continue  # 上流の filter (tooluse 系は別経路) を保持
            performance = benchmark_fn(agent)
            iter_test_count += 1
            tested_cases.append({**agent, "performance": performance})
            if performance > current_performance:
                current_agent = agent
                current_performance = performance

        # 3. Recombination
        recombined = recombine(
            task_description=task_description,
            current_agent=current_agent,
            planning_candidate=candidates["planning"],
            reasoning_candidate=candidates["reasoning"],
            tooluse_candidate=candidates["tooluse"],
            memory_candidate=candidates["memory"],
            tested_case=tested_cases,
            chat_fn=chat_fn,
        )
        filtered_recombined = [a for a in recombined if a["tooluse"] == "None"]
        if not filtered_recombined:
            test_counts["total"] += iter_test_count
            test_counts["iterations"].append(iter_test_count)
            best_performances.append(current_performance)
            agent_counts.append(test_counts["total"])
            continue

        # 4. Predict performance
        predicted = predict_performance(
            chat_fn=chat_fn,
            candidates=candidates,
            archives=archives,
            agents=filtered_recombined,
            golden_cases=golden_cases,
            task_description=task_description,
        )

        # 5. Test top predicted agent
        if predicted:
            best_idx = predicted.index(max(predicted))
            top_agent = filtered_recombined[best_idx]
            performance = benchmark_fn(top_agent)
            iter_test_count += 1
            tested_cases.append({**top_agent, "performance": performance})
            if performance > current_performance:
                current_agent = top_agent
                current_performance = performance

        test_counts["total"] += iter_test_count
        test_counts["iterations"].append(iter_test_count)
        best_performances.append(current_performance)
        agent_counts.append(test_counts["total"])

        _save_json(current_agent, f"current_agent_iteration_{iteration}.json", output_dir)
        _save_json(tested_cases, f"tested_cases_iteration_{iteration}.json", output_dir)

    _save_json(current_agent, "current_agent_final.json", output_dir)
    _save_json(tested_cases, "tested_cases_final.json", output_dir)

    return {
        "best_agent": current_agent,
        "best_performance": current_performance,
        "tested_cases": tested_cases,
        "test_counts": test_counts,
        "best_performances": best_performances,
        "agent_counts": agent_counts,
    }
