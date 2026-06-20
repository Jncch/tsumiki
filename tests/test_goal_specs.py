"""TaskSpec / EvaluatorSpec dataclass のテスト. Phase 5c-1."""

from __future__ import annotations

import pytest

from tsumiki.goal import (
    EvaluatorSpec,
    InputRole,
    KnowledgeSource,
    OutputSchema,
    TaskSpec,
    TestCase,
)


def _make_task_spec() -> TaskSpec:
    return TaskSpec(
        task_class="detect_and_modify",
        domain="nda",
        input_roles=(
            InputRole(
                name="target_document",
                formats=("pdf", "docx", "md"),
                role="target",
            ),
        ),
        knowledge=KnowledgeSource(
            source_type="existing",
            catalog_path="knowledge/skills/nda/ng_patterns/",
        ),
        outputs=(
            OutputSchema(name="findings", schema_id="ng_findings_v1"),
            OutputSchema(name="modified_document", schema_id="modified_text_v1"),
        ),
        raw_goal="NDA をレビューして NG 条項を直したい",
    )


def test_task_spec_io_signature_sorted() -> None:
    spec = _make_task_spec()
    inputs, outputs = spec.io_signature()
    # 入力は (name, role) のソート済みタプル
    assert inputs == (("target_document", "target"),)
    # 出力も name でソート
    assert outputs == (
        ("findings", "ng_findings_v1"),
        ("modified_document", "modified_text_v1"),
    )


def test_task_spec_signature_stable_across_input_order() -> None:
    spec_a = _make_task_spec()
    spec_b = TaskSpec(
        task_class=spec_a.task_class,
        domain=spec_a.domain,
        input_roles=spec_a.input_roles,
        knowledge=spec_a.knowledge,
        outputs=spec_a.outputs[::-1],  # 順序入れ替え
    )
    assert spec_a.io_signature() == spec_b.io_signature()


def test_evaluator_spec_deterministic_no_guardrail_required() -> None:
    spec = EvaluatorSpec(
        id="nda_v1",
        domain="nda",
        task_class="detect_and_modify",
        type="deterministic",
        input_signature=(
            (("target_document", "target"),),
            (("findings", "ng_findings_v1"),),
        ),
        output_metrics=("success_rate",),
        implementation="def evaluate(o): return {}",
        test_cases=(),
        guardrails=(),
        sources=("phase1-4 既存実装",),
        generated_at="2026-06-19",
        approved_by="jncch",
    )
    assert spec.type == "deterministic"
    assert spec.guardrails == ()


def test_evaluator_spec_llm_judge_requires_guardrail() -> None:
    with pytest.raises(ValueError, match="must have at least one guardrail"):
        EvaluatorSpec(
            id="nda_v1",
            domain="nda",
            task_class="detect_and_modify",
            type="llm_judge",
            input_signature=((), ()),
            output_metrics=(),
            implementation="...",
            test_cases=(),
            guardrails=(),
            sources=(),
            generated_at="2026-06-19",
            approved_by="jncch",
        )


def test_evaluator_spec_hybrid_with_guardrail_ok() -> None:
    spec = EvaluatorSpec(
        id="nda_hybrid",
        domain="nda",
        task_class="detect_and_modify",
        type="hybrid",
        input_signature=((), ()),
        output_metrics=("score",),
        implementation="...",
        test_cases=(TestCase(name="t1", input={}, expected={"score": 1.0}),),
        guardrails=("panel_3",),
        sources=(),
        generated_at="2026-06-19",
        approved_by="jncch",
    )
    assert "panel_3" in spec.guardrails
