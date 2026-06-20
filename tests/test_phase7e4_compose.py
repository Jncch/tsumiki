"""Phase 7e-4: tsumiki.policy.compose の入出力 dataclass + 評価器 gate + run_compose smoke.

設計書 `phase7e_design.md` §6.2 (Phase 7e-4 ゲート) を確認する:
  1. `import tsumiki.policy.compose.run_compose` が通る
  2. `_assert_evaluator_gate_passed` が未承認時に `RuntimeError`
  3. `run_compose(cfg)` が mock chat_fn + benchmark_fn で `ComposeResult` を返す
  4. `ComposeConfig` / `ComposeResult` が frozen dataclass である
  5. `make_openai_json_chat_fn` が呼び出せる (構造確認)
"""

from __future__ import annotations

import importlib
from dataclasses import FrozenInstanceError

import pytest

from tsumiki.goal.specs import (
    EvaluatorSpec,
    KnowledgeSource,
    OutputSchema,
    TaskSpec,
)
from tsumiki.knowledge.schemas.ng_patterns import NGPatternBook
from tsumiki.llm.client import LLMSettings


def _make_dummy_task_spec() -> TaskSpec:
    return TaskSpec(
        task_class="detect",
        domain="nda",
        input_roles=(),
        knowledge=KnowledgeSource(source_type="existing", catalog_path="dummy"),
        outputs=(OutputSchema(name="findings", schema_id="ng_findings_v1"),),
        raw_goal="NDA テスト目的",
    )


def _make_dummy_evaluator(approved_by: str) -> EvaluatorSpec:
    return EvaluatorSpec(
        id="dummy_eval",
        domain="nda",
        task_class="detect",
        type="deterministic",
        input_signature=((), ()),
        output_metrics=("findings_recall",),
        implementation="def evaluate(outcomes): return {'findings_recall': 1.0}",
        test_cases=(),
        guardrails=(),
        sources=(),
        generated_at="2026-06-19",
        approved_by=approved_by,
    )


def _make_dummy_knowledge() -> NGPatternBook:
    return NGPatternBook(
        version="0.0.0",
        contract_type="nda",
        last_updated="2026-06-19",
        maintainer="test",
        patterns=(),
    )


def _make_dummy_settings() -> LLMSettings:
    return LLMSettings(
        provider="openai_compatible",
        base_url="http://localhost:11434/v1",
        api_key="dummy",
        model="test-model",
        temperature=0.0,
    )


# === ゲート1: import smoke ===


@pytest.mark.parametrize(
    "module_name",
    [
        "tsumiki.policy.compose",
        "tsumiki.policy.compose.config",
        "tsumiki.policy.compose.runner",
    ],
)
def test_import_compose_modules(module_name: str) -> None:
    mod = importlib.import_module(module_name)
    assert mod is not None


def test_compose_public_api_exists() -> None:
    from tsumiki.policy.compose import (
        BenchmarkFn,
        ChatFn,
        ComposeConfig,
        ComposeResult,
        JsonChatFn,
        _assert_evaluator_gate_passed,
        run_compose,
    )

    assert ComposeConfig is not None
    assert ComposeResult is not None
    assert callable(run_compose)
    assert callable(_assert_evaluator_gate_passed)
    # type aliases (Callable は callable() で True にならない)
    assert ChatFn is not None
    assert JsonChatFn is not None
    assert BenchmarkFn is not None


# === ゲート2: ComposeConfig / ComposeResult が frozen ===


def test_compose_config_is_frozen() -> None:
    from tsumiki.policy.compose import ComposeConfig

    cfg = ComposeConfig(
        task_spec=_make_dummy_task_spec(),
        evaluator_spec=_make_dummy_evaluator(approved_by="auto"),
        knowledge=_make_dummy_knowledge(),
        llm_settings=_make_dummy_settings(),
        chat_fn=lambda _p: "ok",
        json_chat_fn=lambda _m: {},
        benchmark_fn=lambda _a: 0.0,
    )
    with pytest.raises(FrozenInstanceError):
        cfg.max_search_depth = 5  # type: ignore[misc]


def test_compose_result_is_frozen() -> None:
    from tsumiki.policy.compose import ComposeResult

    result = ComposeResult(
        selected_modules={
            "planning": "None",
            "reasoning": "IO",
            "tooluse": "None",
            "memory": "None",
        },
        search_score=0.5,
    )
    with pytest.raises(FrozenInstanceError):
        result.search_score = 1.0  # type: ignore[misc]


# === ゲート3: 評価器 gate ===


def test_assert_evaluator_gate_passed_with_approved() -> None:
    from tsumiki.policy.compose import _assert_evaluator_gate_passed

    evaluator = _make_dummy_evaluator(approved_by="auto")
    # 例外を投げない
    _assert_evaluator_gate_passed(evaluator)


def test_assert_evaluator_gate_passed_raises_when_empty() -> None:
    from tsumiki.policy.compose import _assert_evaluator_gate_passed

    evaluator = _make_dummy_evaluator(approved_by="")
    with pytest.raises(RuntimeError, match="not approved"):
        _assert_evaluator_gate_passed(evaluator)


def test_run_compose_raises_when_evaluator_not_approved() -> None:
    """CLAUDE.md §9: 評価器が無い状態で自動探索を回さない."""
    from tsumiki.policy.compose import ComposeConfig, run_compose

    cfg = ComposeConfig(
        task_spec=_make_dummy_task_spec(),
        evaluator_spec=_make_dummy_evaluator(approved_by=""),
        knowledge=_make_dummy_knowledge(),
        llm_settings=_make_dummy_settings(),
        chat_fn=lambda _p: "ok",
        json_chat_fn=lambda _m: {},
        benchmark_fn=lambda _a: 0.0,
    )
    with pytest.raises(RuntimeError, match="not approved"):
        run_compose(cfg)


# === ゲート4: run_compose smoke (mock DI) ===


def test_run_compose_returns_result_with_mock_di() -> None:
    """mock chat_fn + json_chat_fn + benchmark_fn で run_compose が ComposeResult を返す."""
    from tsumiki.policy.compose import ComposeConfig, ComposeResult, run_compose

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
        return 0.42

    cfg = ComposeConfig(
        task_spec=_make_dummy_task_spec(),
        evaluator_spec=_make_dummy_evaluator(approved_by="auto"),
        knowledge=_make_dummy_knowledge(),
        llm_settings=_make_dummy_settings(),
        chat_fn=mock_chat,
        json_chat_fn=mock_json_chat,
        benchmark_fn=mock_benchmark,
        max_search_depth=1,
    )

    result = run_compose(cfg)
    assert isinstance(result, ComposeResult)
    assert set(result.selected_modules.keys()) == {
        "planning",
        "reasoning",
        "tooluse",
        "memory",
    }
    assert isinstance(result.search_score, float)
    assert isinstance(result.search_history, list)
    assert "total" in result.test_counts


# === ゲート5: make_openai_json_chat_fn の構造確認 ===


def test_make_openai_json_chat_fn_returns_callable() -> None:
    """`make_openai_json_chat_fn` が Callable を返す (実呼び出しはせず構造のみ確認)."""
    from tsumiki.data.synthesis import make_openai_json_chat_fn

    class _MockClient:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                def create(**kwargs):
                    class _Choice:
                        class message:
                            content = '{"ok": true}'
                    class _Resp:
                        choices = [_Choice()]
                    return _Resp()

    fn = make_openai_json_chat_fn(
        client=_MockClient(),
        model="test-model",
        temperature=0.0,
        seed=42,
    )
    assert callable(fn)
    result = fn([{"role": "user", "content": "hi"}])
    assert result == {"ok": True}


def test_make_openai_json_chat_fn_handles_invalid_json() -> None:
    """JSON parse 失敗時は `{}` を返す (上流挙動と一致)."""
    from tsumiki.data.synthesis import make_openai_json_chat_fn

    class _MockClient:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                def create(**kwargs):
                    class _Choice:
                        class message:
                            content = "not json"
                    class _Resp:
                        choices = [_Choice()]
                    return _Resp()

    fn = make_openai_json_chat_fn(
        client=_MockClient(),
        model="test-model",
        temperature=0.0,
        seed=42,
    )
    assert fn([{"role": "user", "content": "hi"}]) == {}
