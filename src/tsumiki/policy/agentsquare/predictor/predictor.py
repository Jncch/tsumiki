"""tsumiki: AgentSquare module performance predictor (vendored from Apache-2.0).

Upstream: https://github.com/tsinghua-fib-lab/AgentSquare/blob/8f5b3fe5d8a32f9b59d20370823bef2a2c86928c/search/module_predictor.py
Vendored at Phase 7e-3 (2026-06-19), rewritten at Phase 7e-3.

Phase 7e-3 modifications:
- `from openai import OpenAI` / 自前 `llm_response` を削除. ChatFn DI に統一.
- `from modules_predictor.*` (alfworld bench 統合) の wildcard import を削除. 上流は
  `inspect.getsource(class_name)` でクラスソースを取り出していたが, tsumiki では archives
  に格納された `code` 文字列を直接利用する設計に変更 (alfworld 配下のモジュールが無くても動作).
- `with open('alfworld_results.json', 'r')` のファイル直接読み込みを削除. golden_cases を
  関数引数として外部から渡す形に変更.
- `eval(response)` を `json.loads(response)` に変更 (chat_fn 側で JSON mode 強制).
- `random.seed(42)` は保持 (tsumiki の再現性ルールと一致, CLAUDE.md §4).
- alfworld 固有の `task_description` ハードコードを引数化.
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from typing import Any, TypedDict

ChatFn = Callable[[str], str]


class ModuleInfo(TypedDict):
    thought: str
    name: str
    module_type: str
    code: str
    performance: float


def _build_agent_code(
    task_description: str,
    agent: dict[str, str],
    archives: dict[str, list[ModuleInfo]],
) -> str:
    """Agent 構成から prompt 用 code 文字列を組み立てる. 上流の `get_module_code` と同型だが,
    `inspect.getsource` ではなく archives の `code` フィールドを使う.
    """
    code = task_description + "\n"
    for module_type in ("planning", "reasoning", "tooluse", "memory"):
        name = agent[module_type]
        code += f"{module_type.capitalize()} module: {name}\n"
        if name.lower() == "none":
            continue
        match = next(
            (m for m in archives[module_type] if m["name"].lower() == name.lower()),
            None,
        )
        if match is not None:
            code += match["code"] + "\n"
    return code


def predict_performance(
    chat_fn: ChatFn,
    candidates: dict[str, dict[str, str]],
    archives: dict[str, list[ModuleInfo]],
    agents: list[dict[str, str]],
    golden_cases: list[dict[str, Any]] | None = None,
    task_description: str = "",
    train_split_ratio: float = 0.8,
    train_max_size: int = 85,
    seed: int = 42,
) -> list[float]:
    """Recombine 等で生成した agent リストの performance を予測する.

    Args:
        chat_fn: prompt -> JSON 文字列を返す ChatFn. JSON mode 強制を推奨.
        candidates: 各 module_type の {name: description} 辞書.
        archives: 各 module_type の ModuleInfo リスト. agent code 生成に使用.
        agents: performance を予測したい agent dict のリスト.
        golden_cases: 既知の (agent, performance) ペアのリスト.
            None の場合は in-context 学習なしで予測 (`train_data=[]` で prompt 構築).
            tsumiki では `eval/generated/` lookup や Phase 5c/6 試走結果から構築する想定.
        task_description: ドメイン記述. 上流は alfworld 固定.
        train_split_ratio: golden_cases の train 比率.
        train_max_size: train 件数の上限.
        seed: golden_cases のシャッフル seed.

    Returns:
        各 agent の予測 performance の float リスト.
    """
    # train_data: in-context learning 用の (prompt_answer, performance) ペアのリスト.
    train_data: list[dict[str, Any]] = []
    if golden_cases:
        # 上流: alfworld_results.json から performance != {} のエントリのみ抽出
        valid_cases = [c for c in golden_cases if c.get("performance") not in (None, {}, "")]
        items = []
        for case in valid_cases:
            code_dict = {
                "planning": case["planning"],
                "reasoning": case["reasoning"],
                "tooluse": case["tooluse"],
                "memory": case["memory"],
                "performance": float(case["performance"]),
            }
            prompt_answer = _build_agent_code(task_description, code_dict, archives)
            items.append(
                {
                    "prompt_answer": prompt_answer,
                    "performance": code_dict["performance"],
                }
            )
        rng = random.Random(seed)
        rng.shuffle(items)
        split = int(len(items) * train_split_ratio)
        train_data = items[:split][:train_max_size]

    # batch: 予測対象 agent の code 文字列リスト
    batch: list[str] = []
    for agent in agents:
        agent_code = _build_agent_code(task_description, agent, archives)
        batch.append(agent_code)

    prompt = (
        f"You are a performance estimator. Now you need to estimate the performance of a "
        f"LLM-based agent solving a task. The agent is composed of four fundamental modules: "
        f"planning, reasoning, tool use and memory. Task description: {task_description} "
        f"Planning module candidates and descriptions: {candidates['planning']}, "
        f"Reasoning module candidates and descriptions: {candidates['reasoning']}, "
        f"Tool use module candidates and descriptions: {candidates['tooluse']}, "
        f"Memory module candidates and descriptions: {candidates['memory']}. "
        f"The performance of some existing module combinations: {train_data}. "
        f"The module combination you need to predict: {batch}. "
        f"You're going to have to predict each of the {len(batch)} combinations I've given you. "
        f"Be sure to give exact predictions. Your output should be of the following json format:"
        + "{'predictions':[{'planning':'deps', 'reasoning':'io', 'tooluse':'None', "
        + "'memory':'dilu', 'performance': ''}]}"
    )

    response = chat_fn(prompt)

    try:
        parsed = json.loads(response)
        result = parsed.get("predictions", [])
    except json.JSONDecodeError:
        result = []

    # Fill missing predictions with 0.0 (上流と同型 fallback)
    while len(result) < len(batch):
        result.append(
            {
                "planning": "None",
                "reasoning": "None",
                "tooluse": "None",
                "memory": "None",
                "performance": 0.0,
            }
        )

    perfs: list[float] = []
    for pred in result[: len(batch)]:
        try:
            perfs.append(float(pred.get("performance", 0.0) or 0.0))
        except (ValueError, TypeError):
            perfs.append(0.0)
    return perfs
