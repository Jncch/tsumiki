"""goal/generator.py + verifier.py のテスト. LLM 応答をスタブ化."""

from __future__ import annotations

import json
import textwrap

import pytest

from tsumiki.goal import (
    InputRole,
    KnowledgeSource,
    OutputSchema,
    TaskSpec,
)
from tsumiki.goal.generator import (
    build_generate_prompt,
    generate_evaluator,
)
from tsumiki.goal.verifier import verify


def _make_task_spec() -> TaskSpec:
    return TaskSpec(
        task_class="detect_and_modify",
        domain="nda",
        input_roles=(
            InputRole(name="target_document", formats=("md",), role="target"),
        ),
        knowledge=KnowledgeSource(source_type="existing", catalog_path="x"),
        outputs=(
            OutputSchema(name="findings", schema_id="ng_findings_v1"),
            OutputSchema(name="modified_document", schema_id="modified_text_v1"),
        ),
    )


_DETERMINISTIC_IMPL = textwrap.dedent(
    '''
    from collections import defaultdict


    def evaluate(outcomes):
        n = len(outcomes)
        if n == 0:
            return {
                "n_samples": 0,
                "modification_success_rate": 0.0,
                "negative_transfer_rate": 0.0,
            }
        removed = sum(1 for r in outcomes if r.get("target_removed"))
        nt = sum(1 for r in outcomes if r.get("new_ng_introduced"))
        return {
            "n_samples": n,
            "modification_success_rate": removed / n,
            "negative_transfer_rate": nt / n,
        }
    '''
).strip()


def _deterministic_response() -> str:
    return json.dumps(
        {
            "id": "nda_modification_success_v1",
            "type": "deterministic",
            "output_metrics": [
                "modification_success_rate",
                "negative_transfer_rate",
            ],
            "implementation": _DETERMINISTIC_IMPL,
            "test_cases": [
                {
                    "name": "empty",
                    "input": {"outcomes": []},
                    "expected": {"modification_success_rate": 0.0},
                },
                {
                    "name": "one_success",
                    "input": {
                        "outcomes": [
                            {
                                "target_removed": True,
                                "new_ng_introduced": False,
                            }
                        ]
                    },
                    "expected": {"modification_success_rate": 1.0},
                },
                {
                    "name": "one_failure",
                    "input": {
                        "outcomes": [
                            {
                                "target_removed": False,
                                "new_ng_introduced": True,
                            }
                        ]
                    },
                    "expected": {"modification_success_rate": 0.0},
                },
            ],
            "guardrails": [],
            "sources": ["src/tsumiki/eval/modification.py"],
            "notes": "Phase 1〜4 互換",
        },
        ensure_ascii=False,
    )


def test_generate_evaluator_basic() -> None:
    task = _make_task_spec()
    spec = generate_evaluator(
        task,
        lambda _: _deterministic_response(),
        generated_at="2026-06-19",
        approved_by="jncch",
    )
    assert spec.id == "nda_modification_success_v1"
    assert spec.domain == task.domain
    assert spec.task_class == task.task_class
    assert spec.type == "deterministic"
    assert spec.input_signature == task.io_signature()
    assert "modification_success_rate" in spec.output_metrics
    assert spec.guardrails == ()
    assert len(spec.test_cases) == 3


def test_generated_implementation_verifies() -> None:
    task = _make_task_spec()
    spec = generate_evaluator(
        task,
        lambda _: _deterministic_response(),
        generated_at="2026-06-19",
    )
    result = verify(spec)
    assert result.error is None
    assert result.passed is True, f"failures: {result.failures}"


def test_generator_llm_judge_requires_guardrail() -> None:
    """LLM が type=llm_judge を返したが guardrails が空の場合は EvaluatorSpec 生成で失敗."""
    task = _make_task_spec()
    bad_response = json.dumps(
        {
            "id": "judge_v1",
            "type": "llm_judge",
            "output_metrics": ["score"],
            "implementation": "def evaluate(o): return {}",
            "test_cases": [],
            "guardrails": [],
            "sources": [],
            "notes": "",
        }
    )
    with pytest.raises(ValueError, match="must have at least one guardrail"):
        generate_evaluator(task, lambda _: bad_response, generated_at="2026-06-19")


def test_build_generate_prompt_unknown_version() -> None:
    task = _make_task_spec()
    with pytest.raises(ValueError, match="unsupported prompt_version"):
        build_generate_prompt(task, prompt_version="v9.9")


def test_verify_detects_mismatch() -> None:
    task = _make_task_spec()
    response = json.dumps(
        {
            "id": "bad_v1",
            "type": "deterministic",
            "output_metrics": ["x"],
            "implementation": "def evaluate(outcomes):\n    return {'x': 0.0}\n",
            "test_cases": [
                {"name": "must_be_one", "input": {"outcomes": []}, "expected": {"x": 1.0}}
            ],
            "guardrails": [],
            "sources": [],
            "notes": "",
        }
    )
    spec = generate_evaluator(task, lambda _: response, generated_at="2026-06-19")
    result = verify(spec)
    assert result.passed is False
    assert any("x mismatch" in f for f in result.failures)


def test_verify_implementation_with_syntax_error() -> None:
    task = _make_task_spec()
    response = json.dumps(
        {
            "id": "broken_v1",
            "type": "deterministic",
            "output_metrics": ["x"],
            "implementation": "def evaluate(outcomes):\n    return {'x':\n",
            "test_cases": [],
            "guardrails": [],
            "sources": [],
            "notes": "",
        }
    )
    spec = generate_evaluator(task, lambda _: response, generated_at="2026-06-19")
    result = verify(spec)
    assert result.passed is False
    assert result.error is not None
