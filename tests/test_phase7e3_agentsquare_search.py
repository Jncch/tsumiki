"""Phase 7e-3: AgentSquare module_evolution / recombination / predictor / search の
import smoke + 関数 DI 動作確認.

設計書 `phase7e_design.md` §6 (7e-3 ゲート) を確認する:
  1. `import tsumiki.policy.agentsquare.{evolution,recombination,predictor,search}` が通る
  2. 各 entry 関数が mock chat_fn / json_chat_fn / benchmark_fn で実行できる
  3. 上流 archive (4 JSON) が読み込める
  4. langchain / utils / openai / planning_prompt 等の旧依存が削除されている
"""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

# === ゲート1: import smoke ===


@pytest.mark.parametrize(
    "module_name",
    [
        "tsumiki.policy.agentsquare.evolution",
        "tsumiki.policy.agentsquare.evolution.evolve",
        "tsumiki.policy.agentsquare.evolution.prompts",
        "tsumiki.policy.agentsquare.evolution.prompts.reasoning",
        "tsumiki.policy.agentsquare.evolution.prompts.planning",
        "tsumiki.policy.agentsquare.evolution.prompts.memory",
        "tsumiki.policy.agentsquare.evolution.prompts.tooluse",
        "tsumiki.policy.agentsquare.recombination",
        "tsumiki.policy.agentsquare.recombination.recombine",
        "tsumiki.policy.agentsquare.predictor",
        "tsumiki.policy.agentsquare.predictor.predictor",
        "tsumiki.policy.agentsquare.search",
        "tsumiki.policy.agentsquare.search.loop",
    ],
)
def test_import_phase7e3_modules(module_name: str) -> None:
    mod = importlib.import_module(module_name)
    assert mod is not None


# === ゲート2: prompts の entry 関数が呼べる + archive 件数確認 ===


def test_prompts_init_archives_sizes() -> None:
    from tsumiki.policy.agentsquare.evolution import (
        get_init_archive_memory,
        get_init_archive_planning,
        get_init_archive_reasoning,
        get_init_archive_tooluse,
    )

    # 上流の固定数 (Phase 7a §3 で確認した entry 数)
    assert len(get_init_archive_reasoning()) == 7
    assert len(get_init_archive_planning()) == 5
    assert len(get_init_archive_memory()) == 4
    assert len(get_init_archive_tooluse()) == 4


def test_prompts_get_prompt_returns_pair() -> None:
    """get_prompt_X が (system_prompt, user_prompt) のタプルを返す."""
    from tsumiki.policy.agentsquare.evolution import (
        get_init_archive_reasoning,
        get_prompt_reasoning,
    )

    archive = get_init_archive_reasoning()
    sys_prompt, user_prompt = get_prompt_reasoning(archive)
    assert isinstance(sys_prompt, str) and len(sys_prompt) > 0
    assert isinstance(user_prompt, str) and "[ARCHIVE]" not in user_prompt


def test_prompts_get_prompt_accepts_feedback_kwarg() -> None:
    """search/module_evolution.py 互換のため last_feedback を受け取れる."""
    from tsumiki.policy.agentsquare.evolution import (
        get_init_archive_planning,
        get_prompt_planning,
    )

    archive = get_init_archive_planning()
    sys_prompt, user_prompt = get_prompt_planning(archive, last_feedback="some feedback")
    assert isinstance(sys_prompt, str)
    assert isinstance(user_prompt, str)


# === ゲート3: evolve() の DI 動作 ===


def test_evolve_with_mock_json_chat_fn(tmp_path: Path) -> None:
    """mock json_chat_fn で evolve() が 4 つの新 agent を返す."""
    from tsumiki.policy.agentsquare.evolution import (
        evolve,
        get_init_archive_memory,
        get_init_archive_planning,
        get_init_archive_reasoning,
        get_init_archive_tooluse,
    )

    call_count = {"n": 0}

    def mock_json_chat(_msg_list):
        call_count["n"] += 1
        return {
            "name": f"NewModule{call_count['n']}",
            "thought": "mock thought",
            "module type": "reasoning",
            "code": "class NewModule(): pass",
        }

    current_agent = {
        "planning": "IO",
        "reasoning": "IO",
        "tooluse": "None",
        "memory": "None",
    }
    agents, planning, reasoning, memory, tooluse = evolve(
        current_agent,
        planning_archive=get_init_archive_planning(),
        reasoning_archive=get_init_archive_reasoning(),
        tooluse_archive=get_init_archive_tooluse(),
        memory_archive=get_init_archive_memory(),
        json_chat_fn=mock_json_chat,
        output_dir=tmp_path,
    )
    assert len(agents) == 4
    # 各 agent は 1 module のみ変更されている
    for a in agents:
        assert set(a.keys()) == {"planning", "reasoning", "tooluse", "memory"}
    # json_chat_fn が 4 回 (planning/reasoning/memory/tooluse) 呼ばれた
    assert call_count["n"] == 4
    # output jsonl 4 件
    assert (tmp_path / "output_reasoning.jsonl").exists()
    assert (tmp_path / "output_planning.jsonl").exists()
    assert (tmp_path / "output_memory.jsonl").exists()
    assert (tmp_path / "output_tooluse.jsonl").exists()
    # planning / reasoning / memory / tooluse は mock の戻り値
    for sol in (planning, reasoning, memory, tooluse):
        assert sol["name"].startswith("NewModule")


# === ゲート4: recombine() の DI 動作 ===


def test_recombine_with_mock_chat_fn() -> None:
    from tsumiki.policy.agentsquare.recombination import recombine

    def mock_chat(_prompt):
        return (
            "{'planning': 'IO', 'reasoning': 'CoT', 'tooluse': 'None', 'memory': 'Dilu'}"
        )

    current_agent = {
        "planning": "IO",
        "reasoning": "IO",
        "tooluse": "None",
        "memory": "None",
    }
    agents = recombine(
        task_description="dummy task",
        current_agent=current_agent,
        planning_candidate={"IO": "io desc", "DEPS": "deps desc"},
        reasoning_candidate={"IO": "io", "CoT": "cot"},
        tooluse_candidate={"None": "none"},
        memory_candidate={"None": "none", "Dilu": "dilu"},
        tested_case=[],
        chat_fn=mock_chat,
    )
    assert len(agents) == 4
    # 2 つ目の agent は reasoning だけ 'CoT' に置換
    assert agents[1]["reasoning"] == "CoT"
    assert agents[1]["planning"] == current_agent["planning"]


def test_recombine_handles_malformed_response() -> None:
    """ast.literal_eval が失敗してもフォールバック (current_agent をそのまま返す)."""
    from tsumiki.policy.agentsquare.recombination import recombine

    def mock_chat(_prompt):
        return "not a valid python dict at all"

    current_agent = {
        "planning": "IO",
        "reasoning": "IO",
        "tooluse": "None",
        "memory": "None",
    }
    agents = recombine(
        task_description="dummy",
        current_agent=current_agent,
        planning_candidate={"IO": "io"},
        reasoning_candidate={"IO": "io"},
        tooluse_candidate={"None": "none"},
        memory_candidate={"None": "none"},
        tested_case=[],
        chat_fn=mock_chat,
    )
    assert len(agents) == 4


# === ゲート5: predict_performance() の DI 動作 ===


def test_predict_performance_with_mock_chat_fn() -> None:
    from tsumiki.policy.agentsquare.predictor import predict_performance

    def mock_chat(_prompt):
        return json.dumps(
            {
                "predictions": [
                    {
                        "planning": "IO",
                        "reasoning": "IO",
                        "tooluse": "None",
                        "memory": "None",
                        "performance": 0.42,
                    },
                    {
                        "planning": "IO",
                        "reasoning": "CoT",
                        "tooluse": "None",
                        "memory": "None",
                        "performance": 0.55,
                    },
                ]
            }
        )

    agents = [
        {"planning": "IO", "reasoning": "IO", "tooluse": "None", "memory": "None"},
        {"planning": "IO", "reasoning": "CoT", "tooluse": "None", "memory": "None"},
    ]
    archives = {k: [] for k in ("planning", "reasoning", "tooluse", "memory")}
    candidates = {
        "planning": {"IO": "io desc"},
        "reasoning": {"IO": "io", "CoT": "cot"},
        "tooluse": {"None": "none"},
        "memory": {"None": "none"},
    }
    perfs = predict_performance(
        chat_fn=mock_chat,
        candidates=candidates,
        archives=archives,
        agents=agents,
        golden_cases=None,
        task_description="dummy",
    )
    assert perfs == [0.42, 0.55]


def test_predict_performance_fallback_on_invalid_json() -> None:
    """JSON parse 失敗時は 0.0 で埋める."""
    from tsumiki.policy.agentsquare.predictor import predict_performance

    def mock_chat(_prompt):
        return "not json"

    agents = [{"planning": "IO", "reasoning": "IO", "tooluse": "None", "memory": "None"}]
    archives = {k: [] for k in ("planning", "reasoning", "tooluse", "memory")}
    candidates = {k: {"IO": "io"} for k in ("planning", "reasoning", "tooluse", "memory")}
    perfs = predict_performance(
        chat_fn=mock_chat,
        candidates=candidates,
        archives=archives,
        agents=agents,
    )
    assert perfs == [0.0]


# === ゲート6: search archives 読み込み + run_search smoke ===


def test_load_default_archives_returns_4_types() -> None:
    from tsumiki.policy.agentsquare.search import MODULE_TYPES, load_default_archives

    candidates, archives = load_default_archives()
    for module_type in MODULE_TYPES:
        assert module_type in candidates
        assert module_type in archives
        assert len(candidates[module_type]) > 0
        assert len(archives[module_type]) > 0


def test_run_search_with_mock_di_smoke() -> None:
    """run_search() が mock DI で 1 iteration 動作する (smoke test)."""
    from tsumiki.policy.agentsquare.search import run_search

    def mock_chat(_prompt):
        return (
            "{'planning': 'IO', 'reasoning': 'IO', 'tooluse': 'None', 'memory': 'None'}"
        )

    def mock_json_chat(_msg_list):
        return {
            "name": "MockModule",
            "thought": "mock",
            "module type": "reasoning",
            "code": "pass",
        }

    def mock_benchmark(_agent):
        return 0.5

    result = run_search(
        benchmark_fn=mock_benchmark,
        chat_fn=mock_chat,
        json_chat_fn=mock_json_chat,
        task_description="dummy task",
        num_iterations=1,
        output_dir=None,
    )
    assert "best_agent" in result
    assert "best_performance" in result
    assert "tested_cases" in result
    assert isinstance(result["best_performance"], float)


# === ゲート7: 旧依存が削除されている ===


_VENDORED_FILES = [
    "evolution/evolve.py",
    "evolution/prompts/reasoning.py",
    "evolution/prompts/planning.py",
    "evolution/prompts/memory.py",
    "evolution/prompts/tooluse.py",
    "recombination/recombine.py",
    "predictor/predictor.py",
    "search/loop.py",
]


_FORBIDDEN_MODULE_PREFIXES = (
    "langchain",
    "utils",
    "openai",
    "planning_prompt",
    "tooluse_IO_pool",
    "modules_predictor",
    "backoff",
    "tenacity",
)


@pytest.mark.parametrize("vendored", _VENDORED_FILES)
def test_no_forbidden_imports(vendored: str) -> None:
    """vendored ファイルの実 import (ast 解釈後) に旧依存が残っていない.

    7e-2 では行頭正規表現で判定していたが, prompts ファイルは長大な docstring 内に
    alfworld archive のサンプル code として `from langchain ...` 等の文字列リテラルを
    含む. これは Python としては実行されない. ast で本体 import のみを抽出する.
    """
    path = (
        Path(__file__).resolve().parent.parent
        / "src" / "tsumiki" / "policy" / "agentsquare" / vendored
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root not in _FORBIDDEN_MODULE_PREFIXES, (
                    f"{vendored}:行 {node.lineno} に `import {alias.name}` が残っている"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            root = node.module.split(".")[0]
            assert root not in _FORBIDDEN_MODULE_PREFIXES, (
                f"{vendored}:行 {node.lineno} に "
                f"`from {node.module} import ...` が残っている"
            )
