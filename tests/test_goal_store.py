"""EvaluatorSpec の保存・読み込みテスト. Phase 5c-1."""

from __future__ import annotations

from pathlib import Path

import pytest

from tsumiki.goal import EvaluatorSpec, TestCase
from tsumiki.goal.store import EVALUATOR_PY, META_YAML, README_MD, TEST_CASES_JSONL, load, save


def _make_spec() -> EvaluatorSpec:
    return EvaluatorSpec(
        id="nda_detect_and_modify_v1",
        domain="nda",
        task_class="detect_and_modify",
        type="deterministic",
        input_signature=(
            (("target_document", "target"),),
            (
                ("findings", "ng_findings_v1"),
                ("modified_document", "modified_text_v1"),
            ),
        ),
        output_metrics=("modification_success_rate", "negative_transfer_rate"),
        implementation="def evaluate(outcomes):\n    return {'success_rate': 0.5}\n",
        test_cases=(
            TestCase(
                name="empty",
                input={"outcomes": []},
                expected={"success_rate": 0.0},
            ),
            TestCase(
                name="all_removed",
                input={"outcomes": [{"target_removed": True}]},
                expected={"success_rate": 1.0},
            ),
        ),
        guardrails=(),
        sources=("src/tsumiki/eval/modification.py", "Phase 2 baseline v0"),
        generated_at="2026-06-19",
        approved_by="jncch",
        notes="Phase 5b で確定した Agent Skills 形式を前提",
    )


def test_save_creates_four_files(tmp_path: Path) -> None:
    spec = _make_spec()
    out_dir = save(tmp_path, spec)
    assert (out_dir / EVALUATOR_PY).is_file()
    assert (out_dir / META_YAML).is_file()
    assert (out_dir / TEST_CASES_JSONL).is_file()
    assert (out_dir / README_MD).is_file()


def test_save_path_structure(tmp_path: Path) -> None:
    spec = _make_spec()
    out_dir = save(tmp_path, spec)
    rel = out_dir.relative_to(tmp_path)
    assert rel.parts == ("nda", "detect_and_modify", "nda_detect_and_modify_v1")


def test_roundtrip(tmp_path: Path) -> None:
    spec = _make_spec()
    out_dir = save(tmp_path, spec)
    loaded = load(out_dir)
    assert loaded.id == spec.id
    assert loaded.domain == spec.domain
    assert loaded.task_class == spec.task_class
    assert loaded.type == spec.type
    assert loaded.input_signature == spec.input_signature
    assert loaded.output_metrics == spec.output_metrics
    assert loaded.implementation == spec.implementation
    assert loaded.test_cases == spec.test_cases
    assert loaded.guardrails == spec.guardrails
    assert loaded.sources == spec.sources
    assert loaded.generated_at == spec.generated_at
    assert loaded.approved_by == spec.approved_by
    assert loaded.notes == spec.notes


def test_load_missing_meta_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="meta.yaml not found"):
        load(tmp_path)


def test_readme_contains_basics(tmp_path: Path) -> None:
    spec = _make_spec()
    out_dir = save(tmp_path, spec)
    readme = (out_dir / README_MD).read_text(encoding="utf-8")
    assert spec.id in readme
    assert spec.domain in readme
    assert spec.task_class in readme
    assert "modification_success_rate" in readme
