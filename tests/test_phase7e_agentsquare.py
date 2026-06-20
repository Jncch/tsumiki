"""Phase 7e-2: AgentSquare vendored モジュールの import smoke + DI 動作確認.

設計書 `phase7e_design.md` §6 (7e-2 ゲート) を確認する:
  1. `import tsumiki.policy.agentsquare.{memory,planning,reasoning,tooluse}` が通る
  2. 各 Base クラスが mock chat_fn で初期化できる
  3. 全 variant クラスが存在し, 上流のクラス名と一致
  4. langchain / utils / planning_prompt / tooluse_IO_pool 依存が削除されている
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def mock_chat_fn():
    """ChatFn の最小実装. 渡された prompt を全部 echo して返すだけ."""
    return lambda prompt: f"[mock-response] {prompt[:50]}"


# === ゲート1: import smoke ===


@pytest.mark.parametrize(
    "module_name",
    [
        "tsumiki.policy.agentsquare",
        "tsumiki.policy.agentsquare.memory",
        "tsumiki.policy.agentsquare.planning",
        "tsumiki.policy.agentsquare.reasoning",
        "tsumiki.policy.agentsquare.tooluse",
    ],
)
def test_import_agentsquare_modules(module_name: str) -> None:
    mod = importlib.import_module(module_name)
    assert mod is not None


# === ゲート2: 各 Base クラスが mock chat_fn で初期化できる ===


def test_memory_base_init_with_chat_fn(mock_chat_fn) -> None:
    from tsumiki.policy.agentsquare.memory import MemoryBase

    base = MemoryBase(chat_fn=mock_chat_fn, llms_type=["gpt-test"])
    assert base.llm_type == "gpt-test"


def test_planning_base_init_with_chat_fn(mock_chat_fn) -> None:
    from tsumiki.policy.agentsquare.planning import PlanningBase

    base = PlanningBase(chat_fn=mock_chat_fn, llms_type=["gpt-test"])
    assert base.llm_type == "gpt-test"
    assert base.plan == []


def test_reasoning_base_init_with_chat_fn(mock_chat_fn) -> None:
    from tsumiki.policy.agentsquare.reasoning import ReasoningBase

    base = ReasoningBase(
        profile_type_prompt="any",
        memory=None,
        chat_fn=mock_chat_fn,
        llms_type=["gpt-test"],
    )
    assert base.llm_type == "gpt-test"


def test_tooluse_base_init_with_chat_fn(mock_chat_fn) -> None:
    from tsumiki.policy.agentsquare.tooluse import ToolUseBase

    base = ToolUseBase(chat_fn=mock_chat_fn, llms_type=["gpt-test"])
    assert base.llm_type == "gpt-test"
    assert base.tool_pool == {}


# === ゲート3: variant クラス存在確認 ===


def test_memory_variants_exist() -> None:
    from tsumiki.policy.agentsquare import memory

    for name in ("MemoryBase", "MemoryDILU", "MemoryGenerative", "MemoryTP", "MemoryVoyager"):
        assert hasattr(memory, name), f"memory に {name} がない"


def test_planning_variants_exist() -> None:
    from tsumiki.policy.agentsquare import planning

    for name in (
        "PlanningBase",
        "PlanningIO",
        "PlanningDEPS",
        "PlanningTD",
        "PlanningVoyager",
        "PlanningOPENAGI",
        "PlanningHUGGINGGPT",
    ):
        assert hasattr(planning, name), f"planning に {name} がない"


def test_reasoning_variants_exist() -> None:
    from tsumiki.policy.agentsquare import reasoning

    for name in (
        "ReasoningBase",
        "ReasoningIO",
        "ReasoningCOT",
        "ReasoningCOTSC",
        "ReasoningTOT",
        "ReasoningDILU",
        "ReasoningSelfRefine",
        "ReasoningStepBack",
        "ReasoningSelfReflectiveTOT",
    ):
        assert hasattr(reasoning, name), f"reasoning に {name} がない"


def test_tooluse_variants_exist() -> None:
    """7e-2 で ToolUseToolBench / ToolUseToolBenchFormer は削除 (langchain Chroma 依存)."""
    from tsumiki.policy.agentsquare import tooluse

    for name in ("ToolUseBase", "ToolUseIO", "ToolUseAnyTool", "ToolUseToolFormer"):
        assert hasattr(tooluse, name), f"tooluse に {name} がない"
    for removed in ("ToolUseToolBench", "ToolUseToolBenchFormer"):
        assert not hasattr(tooluse, removed), (
            f"langchain Chroma 依存の {removed} は 7e-2 で削除済のはず"
        )


# === ゲート4: 旧依存が削除されている ===


@pytest.mark.parametrize(
    "module_name",
    ["memory", "planning", "reasoning", "tooluse"],
)
def test_no_langchain_or_utils_import(module_name: str) -> None:
    """vendored ファイルの行頭 import に langchain / utils / planning_prompt / tooluse_IO_pool /
    openai の直接 import が残っていない (docstring の説明文は除外)."""
    import re as _re
    from pathlib import Path

    path = (
        Path(__file__).resolve().parent.parent
        / "src" / "tsumiki" / "policy" / "agentsquare" / f"{module_name}.py"
    )
    forbidden_prefixes = [
        r"^from langchain",
        r"^import langchain",
        r"^from utils\s",
        r"^from planning_prompt\s",
        r"^from tooluse_IO_pool\s",
        r"^from openai\s",
    ]
    for line in path.read_text(encoding="utf-8").splitlines():
        for pat in forbidden_prefixes:
            assert not _re.match(pat, line), (
                f"{module_name}.py:行 `{line}` に旧依存 import が残っている"
            )


# === ゲート5: ChatFn DI 動作確認 (基本 1 例ずつ) ===


def test_planning_io_call_uses_chat_fn(mock_chat_fn) -> None:
    """PlanningIO の __call__ が chat_fn を呼ぶ (戻り値の構造は気にしない)."""
    from tsumiki.policy.agentsquare.planning import PlanningIO

    planner = PlanningIO(chat_fn=mock_chat_fn, llms_type=["gpt-test"])
    # __call__ は dict_strings を ast.literal_eval するため,
    # mock の echo 戻り値には dict が含まれず空 list が返る.
    result = planner("test_type", "test task", "", "few_shot example")
    assert result == []


def test_simple_memory_store_basic_ops() -> None:
    """memory.py の _SimpleMemoryStore (langchain Chroma 代替) の基本動作."""
    from tsumiki.policy.agentsquare.memory import _SimpleMemoryStore

    store = _SimpleMemoryStore()
    assert store.count() == 0
    store.add(page_content="abc", metadata={"task_trajectory": "traj1"})
    store.add(page_content="def", metadata={"task_trajectory": "traj2"})
    assert store.count() == 2
    results = store.search("abc", k=1)
    assert len(results) == 1
    assert results[0]["metadata"]["task_trajectory"] == "traj1"
