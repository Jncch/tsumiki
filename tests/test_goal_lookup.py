"""流用蓄積からの評価器検索テスト. Phase 5c-1."""

from __future__ import annotations

from pathlib import Path

from tsumiki.goal import (
    EvaluatorSpec,
    InputRole,
    KnowledgeSource,
    OutputSchema,
    TaskSpec,
)
from tsumiki.goal.lookup import search
from tsumiki.goal.store import save


def _make_task_spec(domain: str = "nda", task_class: str = "detect_and_modify") -> TaskSpec:
    return TaskSpec(
        task_class=task_class,
        domain=domain,
        input_roles=(
            InputRole(name="target_document", formats=("md",), role="target"),
        ),
        knowledge=KnowledgeSource(source_type="existing", catalog_path="x"),
        outputs=(
            OutputSchema(name="findings", schema_id="ng_findings_v1"),
            OutputSchema(name="modified_document", schema_id="modified_text_v1"),
        ),
    )


def _make_evaluator(
    *,
    id: str,
    domain: str,
    task_class: str,
    matches: TaskSpec | None = None,
) -> EvaluatorSpec:
    if matches is not None:
        sig = matches.io_signature()
    else:
        sig = ((("other", "target"),), (("other", "schema_v1"),))
    return EvaluatorSpec(
        id=id,
        domain=domain,
        task_class=task_class,
        type="deterministic",
        input_signature=sig,
        output_metrics=("metric_a",),
        implementation="def evaluate(o): return {}",
        test_cases=(),
        guardrails=(),
        sources=(),
        generated_at="2026-06-19",
        approved_by="jncch",
    )


def test_empty_root_returns_no_candidates(tmp_path: Path) -> None:
    task = _make_task_spec()
    assert search(tmp_path, task) == []


def test_exact_match_found(tmp_path: Path) -> None:
    task = _make_task_spec()
    spec = _make_evaluator(
        id="nda_v1", domain="nda", task_class="detect_and_modify", matches=task
    )
    save(tmp_path, spec)
    results = search(tmp_path, task)
    assert len(results) == 1
    assert results[0].exact_match is True
    assert results[0].spec.id == "nda_v1"


def test_partial_match_only_when_include_partial(tmp_path: Path) -> None:
    task = _make_task_spec()
    other_sig_spec = _make_evaluator(
        id="nda_other_io",
        domain="nda",
        task_class="detect_and_modify",
        matches=None,
    )
    save(tmp_path, other_sig_spec)
    # include_partial=False では 0 件
    assert search(tmp_path, task, include_partial=False) == []
    # include_partial=True で 1 件 (partial)
    results = search(tmp_path, task, include_partial=True)
    assert len(results) == 1
    assert results[0].exact_match is False


def test_different_domain_excluded(tmp_path: Path) -> None:
    task = _make_task_spec(domain="nda")
    spec = _make_evaluator(
        id="iso27001_v1",
        domain="iso27001",
        task_class="detect_and_modify",
        matches=task,
    )
    save(tmp_path, spec)
    assert search(tmp_path, task, include_partial=True) == []


def test_different_task_class_excluded(tmp_path: Path) -> None:
    task = _make_task_spec(task_class="detect_and_modify")
    spec = _make_evaluator(
        id="nda_detect_only",
        domain="nda",
        task_class="detect",
        matches=task,
    )
    save(tmp_path, spec)
    assert search(tmp_path, task, include_partial=True) == []


def test_exact_match_ranked_before_partial(tmp_path: Path) -> None:
    task = _make_task_spec()
    exact = _make_evaluator(
        id="nda_exact", domain="nda", task_class="detect_and_modify", matches=task
    )
    partial = _make_evaluator(
        id="nda_partial", domain="nda", task_class="detect_and_modify", matches=None
    )
    save(tmp_path, exact)
    save(tmp_path, partial)
    results = search(tmp_path, task, include_partial=True)
    assert len(results) == 2
    assert results[0].exact_match is True
    assert results[0].spec.id == "nda_exact"
    assert results[1].exact_match is False
    assert results[1].spec.id == "nda_partial"
