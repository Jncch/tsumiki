"""Phase 9a: TaskClass + OutputKind + InputModality 拡張の構造確認.

設計書 `phase9_design.md` §3.1 / §4.2 9a ゲートに対応.

確認項目:
- TaskClass に Phase 9a 追加分 (generate / compose / summarize / transform / infer) が乗る
- OutputKind / InputModality が Literal として機能する
- TaskSpec のデフォルト (output_kind="closed", input_modality="doc") が既存 NDA/ISO27001
  挙動と互換である
- ヘルパー (is_open_ended / has_document_input / has_input) が直交軸を正しく分類する
- EvaluatorSpec にも output_kind デフォルト "closed" が乗る
"""

from __future__ import annotations

import pytest

from tsumiki.goal.specs import (
    EvaluatorSpec,
    InputModality,
    InputRole,
    KnowledgeSource,
    OutputKind,
    OutputSchema,
    TaskClass,
    TaskSpec,
    TestCase,
)


def _make_minimal_inputs() -> tuple[InputRole, ...]:
    return (
        InputRole(name="target_document", formats=("md",), role="target"),
    )


def _make_minimal_knowledge() -> KnowledgeSource:
    return KnowledgeSource(source_type="existing", catalog_path="knowledge/skills/x")


def _make_minimal_outputs() -> tuple[OutputSchema, ...]:
    return (OutputSchema(name="findings", schema_id="ng_findings_v1"),)


# === TaskClass 新規 5 種類 ===


@pytest.mark.parametrize(
    "task_class",
    [
        "generate",
        "compose",
        "summarize",
        "transform",
        "infer",
    ],
)
def test_task_class_new_values_constructable(task_class: TaskClass) -> None:
    """Phase 9a で追加した 5 種類の TaskClass で TaskSpec が construct できる."""
    spec = TaskSpec(
        task_class=task_class,
        domain="x",
        input_roles=_make_minimal_inputs(),
        knowledge=_make_minimal_knowledge(),
        outputs=_make_minimal_outputs(),
    )
    assert spec.task_class == task_class


@pytest.mark.parametrize(
    "task_class",
    [
        "detect",
        "modify",
        "detect_and_modify",
        "extract",
        "compare",
    ],
)
def test_task_class_legacy_values_still_work(task_class: TaskClass) -> None:
    """既存 5 種類はそのまま動く (リグレッションなし)."""
    spec = TaskSpec(
        task_class=task_class,
        domain="x",
        input_roles=_make_minimal_inputs(),
        knowledge=_make_minimal_knowledge(),
        outputs=_make_minimal_outputs(),
    )
    assert spec.task_class == task_class


# === OutputKind ===


@pytest.mark.parametrize(
    "output_kind",
    ["closed", "semi_open", "open"],
)
def test_output_kind_all_values_constructable(output_kind: OutputKind) -> None:
    spec = TaskSpec(
        task_class="generate",
        domain="x",
        input_roles=_make_minimal_inputs(),
        knowledge=_make_minimal_knowledge(),
        outputs=_make_minimal_outputs(),
        output_kind=output_kind,
    )
    assert spec.output_kind == output_kind


def test_output_kind_default_is_closed() -> None:
    """既存 NDA/ISO27001 互換のためデフォルトは 'closed'."""
    spec = TaskSpec(
        task_class="detect",
        domain="x",
        input_roles=_make_minimal_inputs(),
        knowledge=_make_minimal_knowledge(),
        outputs=_make_minimal_outputs(),
    )
    assert spec.output_kind == "closed"


# === InputModality ===


@pytest.mark.parametrize(
    "modality",
    ["doc", "free_text", "structured", "mixed", "none"],
)
def test_input_modality_all_values_constructable(modality: InputModality) -> None:
    spec = TaskSpec(
        task_class="generate",
        domain="x",
        input_roles=_make_minimal_inputs(),
        knowledge=_make_minimal_knowledge(),
        outputs=_make_minimal_outputs(),
        input_modality=modality,
    )
    assert spec.input_modality == modality


def test_input_modality_default_is_doc() -> None:
    """既存 NDA/ISO27001 互換のためデフォルトは 'doc'."""
    spec = TaskSpec(
        task_class="detect",
        domain="x",
        input_roles=_make_minimal_inputs(),
        knowledge=_make_minimal_knowledge(),
        outputs=_make_minimal_outputs(),
    )
    assert spec.input_modality == "doc"


# === InputRoleKind 拡張 ===


@pytest.mark.parametrize(
    "role_kind",
    ["target", "reference", "rule", "intent", "record", "focus"],
)
def test_input_role_kind_all_values(role_kind: str) -> None:
    """Phase 9a で intent / record / focus を追加. 既存 target / reference / rule も維持."""
    role = InputRole(name="x", formats=("md",), role=role_kind)  # type: ignore[arg-type]
    assert role.role == role_kind


# === ヘルパー ===


@pytest.mark.parametrize(
    "output_kind,expected",
    [
        ("closed", False),
        ("semi_open", True),
        ("open", True),
    ],
)
def test_is_open_ended(output_kind: OutputKind, expected: bool) -> None:
    spec = TaskSpec(
        task_class="generate",
        domain="x",
        input_roles=_make_minimal_inputs(),
        knowledge=_make_minimal_knowledge(),
        outputs=_make_minimal_outputs(),
        output_kind=output_kind,
    )
    assert spec.is_open_ended() is expected


@pytest.mark.parametrize(
    "modality,expected",
    [
        ("doc", True),
        ("mixed", True),
        ("free_text", False),
        ("structured", False),
        ("none", False),
    ],
)
def test_has_document_input(modality: InputModality, expected: bool) -> None:
    spec = TaskSpec(
        task_class="generate",
        domain="x",
        input_roles=_make_minimal_inputs(),
        knowledge=_make_minimal_knowledge(),
        outputs=_make_minimal_outputs(),
        input_modality=modality,
    )
    assert spec.has_document_input() is expected


@pytest.mark.parametrize(
    "modality,expected",
    [
        ("doc", True),
        ("free_text", True),
        ("structured", True),
        ("mixed", True),
        ("none", False),
    ],
)
def test_has_input(modality: InputModality, expected: bool) -> None:
    spec = TaskSpec(
        task_class="compose",
        domain="x",
        input_roles=_make_minimal_inputs(),
        knowledge=_make_minimal_knowledge(),
        outputs=_make_minimal_outputs(),
        input_modality=modality,
    )
    assert spec.has_input() is expected


# === EvaluatorSpec への output_kind 追加 ===


@pytest.mark.parametrize(
    "output_kind",
    ["closed", "semi_open", "open"],
)
def test_evaluator_spec_output_kind(output_kind: OutputKind) -> None:
    spec = EvaluatorSpec(
        id="x_v1",
        domain="x",
        task_class="generate",
        type="deterministic",
        input_signature=((), ()),
        output_metrics=("success_rate",),
        implementation="def evaluate(): return 1",
        test_cases=(TestCase(name="t1", input={}, expected={"score": 1}),),
        guardrails=(),
        sources=(),
        generated_at="2026-06-20",
        approved_by="auto",
        output_kind=output_kind,
    )
    assert spec.output_kind == output_kind


def test_evaluator_spec_output_kind_default_closed() -> None:
    """既存承認済評価器との後方互換のためデフォルトは 'closed'."""
    spec = EvaluatorSpec(
        id="x_v1",
        domain="x",
        task_class="detect",
        type="deterministic",
        input_signature=((), ()),
        output_metrics=("success_rate",),
        implementation="def evaluate(): return 1",
        test_cases=(TestCase(name="t1", input={}, expected={"score": 1}),),
        guardrails=(),
        sources=(),
        generated_at="2026-06-20",
        approved_by="auto",
    )
    assert spec.output_kind == "closed"


# === io_signature() は output_kind / input_modality を含まない (Phase 9b で別途扱う) ===


def test_io_signature_unchanged_by_output_kind() -> None:
    """io_signature の中身は output_kind 追加で変わらない (lookup 後方互換)."""
    base_kwargs = dict(
        task_class="detect" if True else "generate",
        domain="x",
        input_roles=_make_minimal_inputs(),
        knowledge=_make_minimal_knowledge(),
        outputs=_make_minimal_outputs(),
    )
    closed = TaskSpec(**base_kwargs, output_kind="closed")  # type: ignore[arg-type]
    open_ = TaskSpec(**base_kwargs, output_kind="open")  # type: ignore[arg-type]
    assert closed.io_signature() == open_.io_signature()


def test_io_signature_unchanged_by_input_modality() -> None:
    """io_signature の中身は input_modality 追加で変わらない."""
    base_kwargs = dict(
        task_class="generate",
        domain="x",
        input_roles=_make_minimal_inputs(),
        knowledge=_make_minimal_knowledge(),
        outputs=_make_minimal_outputs(),
    )
    doc = TaskSpec(**base_kwargs, input_modality="doc")  # type: ignore[arg-type]
    free = TaskSpec(**base_kwargs, input_modality="free_text")  # type: ignore[arg-type]
    assert doc.io_signature() == free.io_signature()


# === ユースケース例: 3 軸の組合せが意図通りに動く ===


def test_marketing_post_example_spec() -> None:
    """広報原稿: generate × open × free_text の組合せが意図通り構築できる."""
    spec = TaskSpec(
        task_class="generate",
        domain="marketing_post",
        input_roles=(InputRole(name="intent_text", formats=("md",), role="intent"),),
        knowledge=KnowledgeSource(
            source_type="existing", catalog_path="knowledge/skills/marketing_post"
        ),
        outputs=(OutputSchema(name="post_text", schema_id="instagram_post_v1"),),
        output_kind="open",
        input_modality="free_text",
        raw_goal="ビーガン向けプロテインバーの 9 月発売をインスタで訴求したい",
    )
    assert spec.is_open_ended() is True
    assert spec.has_document_input() is False
    assert spec.has_input() is True


def test_meeting_summary_example_spec() -> None:
    """議事録要約: summarize × semi_open × mixed の組合せ."""
    spec = TaskSpec(
        task_class="summarize",
        domain="meeting_minutes",
        input_roles=(
            InputRole(name="transcript", formats=("md", "txt"), role="target"),
            InputRole(name="focus_hint", formats=("txt",), role="focus"),
        ),
        knowledge=KnowledgeSource(
            source_type="existing", catalog_path="knowledge/skills/meeting_minutes"
        ),
        outputs=(OutputSchema(name="summary", schema_id="meeting_summary_v1"),),
        output_kind="semi_open",
        input_modality="mixed",
    )
    assert spec.is_open_ended() is True
    assert spec.has_document_input() is True


def test_campaign_proposal_example_spec() -> None:
    """販促キャンペーン案: compose × open × none (入力なし、目的だけから生成)."""
    spec = TaskSpec(
        task_class="compose",
        domain="marketing_campaign",
        input_roles=(),
        knowledge=KnowledgeSource(
            source_type="existing", catalog_path="knowledge/skills/marketing_campaign"
        ),
        outputs=(OutputSchema(name="campaign_plan", schema_id="campaign_v1"),),
        output_kind="open",
        input_modality="none",
        raw_goal="9 月決算月の販促キャンペーンを考えたい",
    )
    assert spec.is_open_ended() is True
    assert spec.has_document_input() is False
    assert spec.has_input() is False


def test_nda_existing_spec_defaults_unchanged() -> None:
    """既存 NDA TaskSpec を default で作ると closed + doc になり既存挙動互換."""
    spec = TaskSpec(
        task_class="detect_and_modify",
        domain="nda",
        input_roles=(InputRole(name="target_document", formats=("md",), role="target"),),
        knowledge=KnowledgeSource(
            source_type="existing", catalog_path="knowledge/skills/nda"
        ),
        outputs=(
            OutputSchema(name="findings", schema_id="ng_findings_v1"),
            OutputSchema(name="modified_document", schema_id="modified_doc_v1"),
        ),
    )
    assert spec.output_kind == "closed"
    assert spec.input_modality == "doc"
    assert spec.is_open_ended() is False
    assert spec.has_document_input() is True
    assert spec.has_input() is True
