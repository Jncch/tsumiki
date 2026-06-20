"""Phase 9b: 対話 REPL + 評価軸 loader + 質問 loader (YAML 外部化版) の構造確認.

設計 phase9_design §3.2 / §4.2 9b ゲートに対応.
2026-06-20 改訂: Q1〜Q10 を YAML 外部化したため loader 経由の確認に切替.

確認項目:
- eval_dimensions loader が _common/ をロード
- dialog_questions loader が _common/<stage>*.yaml をロード
- ドメイン override が _common を上書き
- Literal 整合性チェック (allowed_values が Literal subset か)
- filter_applicable が task_class + output_kind で正しく絞る
- 6 stage を mock LLM + scripted input で完走
- 対話ログが JSONL で persist
- LLM 提案が空回答時に発火し、選択肢チェックが効く
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tsumiki.goal.dialog import (
    DEFAULT_DIMENSIONS_ROOT,
    DEFAULT_QUESTIONS_ROOT,
    DialogConfig,
    DialogState,
    run_dialog,
    stage1_clarify_goal,
    stage2_select_dimensions,
    stage6_approve,
)
from tsumiki.knowledge.schemas.dialog_questions import (
    DialogQuestion,
    load_all_dialog_questions,
    load_dialog_questions,
)
from tsumiki.knowledge.schemas.eval_dimensions import (
    EvalDimension,
    filter_applicable,
    load_eval_dimensions,
)

DIMENSIONS_ROOT = Path("src/tsumiki/knowledge/schemas/eval_dimensions")
QUESTIONS_ROOT = Path("src/tsumiki/knowledge/schemas/dialog_questions")


# === eval_dimensions loader ===


def test_load_common_dimensions() -> None:
    """_common/ から 5 つの評価軸がロードされる."""
    dims = load_eval_dimensions(DIMENSIONS_ROOT)
    ids = {d.id for d in dims}
    assert "char_limit" in ids
    assert "format_validity" in ids
    assert "keyword_inclusion" in ids
    assert "llm_judge_panel" in ids
    assert "llm_judge_pairwise" in ids
    assert all(d.source_domain == "_common" for d in dims)


def test_load_with_unknown_domain_falls_back_to_common(tmp_path: Path) -> None:
    """存在しないドメインを指定しても _common/ のみがロードされる."""
    dims = load_eval_dimensions(DIMENSIONS_ROOT, domain="nonexistent_domain")
    assert len(dims) >= 5


def test_load_domain_override(tmp_path: Path) -> None:
    """ドメイン固有 YAML が _common/ の同 ID を上書きする."""
    common = tmp_path / "_common"
    common.mkdir()
    (common / "char_limit.yaml").write_text(
        "id: char_limit\nlabel: COMMON\ntype: deterministic\n"
        "applicable_task_classes: [generate]\napplicable_output_kinds: [open]\n",
        encoding="utf-8",
    )
    domain = tmp_path / "marketing_post"
    domain.mkdir()
    (domain / "char_limit.yaml").write_text(
        "id: char_limit\nlabel: MARKETING\ntype: deterministic\n"
        "applicable_task_classes: [generate]\napplicable_output_kinds: [open]\n",
        encoding="utf-8",
    )
    dims = load_eval_dimensions(tmp_path, domain="marketing_post")
    char_limit = next(d for d in dims if d.id == "char_limit")
    assert char_limit.label == "MARKETING"
    assert char_limit.source_domain == "marketing_post"


def test_filter_applicable_by_task_class_and_output_kind() -> None:
    dims = load_eval_dimensions(DIMENSIONS_ROOT)

    applicable = filter_applicable(dims, task_class="generate", output_kind="open")
    ids = {d.id for d in applicable}
    assert "char_limit" in ids
    assert "keyword_inclusion" in ids
    assert "llm_judge_panel" in ids
    assert "format_validity" not in ids

    applicable_detect = filter_applicable(dims, task_class="detect", output_kind="closed")
    assert all(d.id != "char_limit" for d in applicable_detect)


def test_missing_common_directory_raises_for_dimensions(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_eval_dimensions(tmp_path)


# === dialog_questions loader (YAML 外部化版, 2026-06-20 改訂) ===


def test_load_all_dialog_questions_returns_3_stages() -> None:
    """_common/ から 3 stage (task_spec/dimensions/approve) がロードされる."""
    bundle = load_all_dialog_questions(QUESTIONS_ROOT)
    assert bundle.task_spec.stage == "task_spec"
    assert bundle.dimensions.stage == "dimensions"
    assert bundle.approve.stage == "approve"


def test_task_spec_stage_has_8_questions() -> None:
    bundle = load_all_dialog_questions(QUESTIONS_ROOT)
    ids = [q.id for q in bundle.task_spec.questions]
    assert ids == [
        "raw_goal",
        "task_class",
        "output_kind",
        "input_modality",
        "domain",
        "input_roles_csv",
        "outputs_csv",
        "knowledge_catalog_path",
    ]


def test_dimensions_stage_has_one_question() -> None:
    bundle = load_all_dialog_questions(QUESTIONS_ROOT)
    assert len(bundle.dimensions.questions) == 1
    assert bundle.dimensions.questions[0].id == "selected_dimensions"


def test_approve_stage_has_yes_no_question() -> None:
    bundle = load_all_dialog_questions(QUESTIONS_ROOT)
    assert len(bundle.approve.questions) == 1
    assert bundle.approve.questions[0].expected_type == "yes_no"


def test_task_class_question_allowed_values_subset_of_literal() -> None:
    """Q2 (task_class) の allowed_values が TaskClass Literal の subset."""
    bundle = load_all_dialog_questions(QUESTIONS_ROOT)
    q_task = next(q for q in bundle.task_spec.questions if q.id == "task_class")
    assert "generate" in q_task.allowed_values
    assert "detect" in q_task.allowed_values
    assert q_task.validate_against_literal == "TaskClass"


def test_output_kind_question_allowed_values() -> None:
    bundle = load_all_dialog_questions(QUESTIONS_ROOT)
    q = next(q for q in bundle.task_spec.questions if q.id == "output_kind")
    assert set(q.allowed_values) == {"closed", "semi_open", "open"}
    assert q.validate_against_literal == "OutputKind"


def test_input_modality_question_allowed_values() -> None:
    bundle = load_all_dialog_questions(QUESTIONS_ROOT)
    q = next(q for q in bundle.task_spec.questions if q.id == "input_modality")
    assert set(q.allowed_values) == {"doc", "free_text", "structured", "mixed", "none"}
    assert q.validate_against_literal == "InputModality"


def test_literal_integrity_check_rejects_invalid_values() -> None:
    """allowed_values が Literal にない値を含むと __post_init__ で ValueError."""
    with pytest.raises(ValueError, match="allowed_values"):
        DialogQuestion(
            id="bogus",
            prompt="x",
            expected_type="literal",
            allowed_values=("nonexistent_task_class",),
            validate_against_literal="TaskClass",
        )


def test_literal_integrity_check_rejects_unknown_literal_name() -> None:
    """validate_against_literal に未登録の名前を指定すると ValueError."""
    with pytest.raises(ValueError, match="未知の Literal 名"):
        DialogQuestion(
            id="bogus",
            prompt="x",
            expected_type="literal",
            allowed_values=("a",),
            validate_against_literal="UnknownLiteral",
        )


def test_dialog_questions_domain_override(tmp_path: Path) -> None:
    """ドメイン固有 YAML が _common/<stage>*.yaml を override する."""
    common = tmp_path / "_common"
    common.mkdir()
    (common / "stage6_approve.yaml").write_text(
        "stage: approve\ntitle: COMMON\nquestions:\n"
        "  - id: approve\n    prompt: COMMON_PROMPT\n    expected_type: yes_no\n",
        encoding="utf-8",
    )
    domain = tmp_path / "marketing_post"
    domain.mkdir()
    (domain / "stage6_approve.yaml").write_text(
        "stage: approve\ntitle: MARKETING\nquestions:\n"
        "  - id: approve\n    prompt: MARKETING_PROMPT\n    expected_type: yes_no\n",
        encoding="utf-8",
    )
    stage = load_dialog_questions(tmp_path, "approve", domain="marketing_post")
    assert stage.title == "MARKETING"
    assert stage.questions[0].prompt == "MARKETING_PROMPT"
    assert stage.source_domain == "marketing_post"


def test_missing_common_directory_raises_for_questions(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_dialog_questions(tmp_path, "task_spec")


# === scripted I/O ヘルパ ===


def _scripted_input(answers: list[str]) -> tuple[Iterator[str], list[str]]:
    log: list[str] = []
    it = iter(answers)

    def fn(prompt: str) -> str:
        try:
            val = next(it)
        except StopIteration:
            raise RuntimeError(f"想定外の質問 (回答が尽きた): {prompt}") from None
        log.append(f"{prompt} -> {val}")
        return val

    return fn, log  # type: ignore[return-value]


def _collect_output() -> tuple[list[str], list[str]]:
    msgs: list[str] = []

    def fn(msg: str) -> None:
        msgs.append(msg)

    return fn, msgs  # type: ignore[return-value]


# === stage 1 単体 ===


def test_stage1_constructs_task_spec_from_8_answers(tmp_path: Path) -> None:
    config = DialogConfig(
        log_dir=tmp_path / "logs",
        timestamp_fn=lambda: "2026-06-20T12:00:00Z",
    )
    answers = [
        "ビーガン向けプロテインバーの 9 月発売を訴求したい",
        "generate",
        "open",
        "free_text",
        "marketing_post",
        "intent_text:intent",
        "post_text:instagram_post_v1",
        "knowledge/skills/marketing_post",
    ]
    input_fn, _ = _scripted_input(answers)
    output_fn, msgs = _collect_output()

    state = stage1_clarify_goal(DialogState(), config, None, input_fn, output_fn)
    assert state.task_spec is not None
    spec = state.task_spec
    assert spec.task_class == "generate"
    assert spec.output_kind == "open"
    assert spec.input_modality == "free_text"
    assert spec.domain == "marketing_post"
    assert len(spec.input_roles) == 1
    assert spec.input_roles[0].name == "intent_text"
    assert spec.input_roles[0].role == "intent"
    assert len(spec.outputs) == 1
    assert spec.outputs[0].schema_id == "instagram_post_v1"
    assert spec.knowledge.catalog_path == "knowledge/skills/marketing_post"
    assert any("Stage 1" in m for m in msgs)


def test_stage1_invalid_literal_value_raises(tmp_path: Path) -> None:
    config = DialogConfig(log_dir=tmp_path / "logs")
    answers = [
        "目的",
        "INVALID_TASK_CLASS",
        "closed",
        "doc",
        "x",
        "",
        "",
        "",
    ]
    input_fn, _ = _scripted_input(answers)
    output_fn, _ = _collect_output()
    with pytest.raises(ValueError, match="許可されない値"):
        stage1_clarify_goal(DialogState(), config, None, input_fn, output_fn)


# === stage 2 単体 ===


def test_stage2_filters_by_task_class_and_output_kind(tmp_path: Path) -> None:
    config = DialogConfig(log_dir=tmp_path / "logs")
    state = DialogState()
    from tsumiki.goal.specs import KnowledgeSource, TaskSpec

    state.task_spec = TaskSpec(
        task_class="generate",
        domain="marketing_post",
        input_roles=(),
        knowledge=KnowledgeSource(source_type="existing", catalog_path="x"),
        outputs=(),
        output_kind="open",
        input_modality="free_text",
    )
    input_fn, _ = _scripted_input(["char_limit,llm_judge_panel"])
    output_fn, _ = _collect_output()

    state = stage2_select_dimensions(state, config, input_fn, output_fn)
    assert len(state.selected_dimensions) == 2
    assert {d.id for d in state.selected_dimensions} == {"char_limit", "llm_judge_panel"}


def test_stage2_unknown_dimension_raises(tmp_path: Path) -> None:
    config = DialogConfig(log_dir=tmp_path / "logs")
    state = DialogState()
    from tsumiki.goal.specs import KnowledgeSource, TaskSpec

    state.task_spec = TaskSpec(
        task_class="generate",
        domain="x",
        input_roles=(),
        knowledge=KnowledgeSource(source_type="existing", catalog_path="x"),
        outputs=(),
        output_kind="open",
        input_modality="free_text",
    )
    input_fn, _ = _scripted_input(["nonexistent_dim_id"])
    output_fn, _ = _collect_output()
    with pytest.raises(ValueError, match="未知の評価軸"):
        stage2_select_dimensions(state, config, input_fn, output_fn)


# === stage 6 単体 ===


def test_stage6_approve_yes(tmp_path: Path) -> None:
    config = DialogConfig(
        log_dir=tmp_path / "logs",
        timestamp_fn=lambda: "2026-06-20T12:00:00Z",
    )
    input_fn, _ = _scripted_input(["yes"])
    output_fn, _ = _collect_output()
    state = stage6_approve(DialogState(), config, input_fn, output_fn)
    assert state.approved is True
    assert state.approved_by.startswith("user_dialog_2026-06-20T12:00:00Z")


def test_stage6_approve_no(tmp_path: Path) -> None:
    config = DialogConfig(log_dir=tmp_path / "logs")
    input_fn, _ = _scripted_input(["no"])
    output_fn, _ = _collect_output()
    state = stage6_approve(DialogState(), config, input_fn, output_fn)
    assert state.approved is False
    assert state.approved_by == ""


# === 6 stage 完走 + ログ永続化 (9b ゲート本体) ===


def test_run_dialog_full_walkthrough(tmp_path: Path) -> None:
    """mock LLM + scripted input で 6 stage 完走 + ログ JSONL に出る."""
    config = DialogConfig(
        log_dir=tmp_path / "logs",
        timestamp_fn=lambda: "2026-06-20T12:00:00Z",
    )
    answers = [
        "目的: テスト",
        "generate",
        "open",
        "free_text",
        "test_domain",
        "",
        "result:result_v1",
        "",
        "char_limit,keyword_inclusion",
        # Phase 9c で stage3 が本実装になったため、各軸パラメータ + 重み + 厳しさ + 確認を追加
        "",         # char_limit min_chars (default)
        "150",      # char_limit max_chars
        "新発売",   # keyword_inclusion required_keywords
        "",         # keyword_inclusion forbidden_keywords (default)
        "equal",    # Q11 weights_mode
        "balanced", # Q12 strictness
        "yes",      # Q13 draft confirm
        "yes",      # stage6 approve
    ]
    input_fn, _ = _scripted_input(answers)
    output_fn, _ = _collect_output()

    def fake_json_chat(messages: list[dict]) -> dict:
        return {"suggestion": ""}

    state = run_dialog(config, fake_json_chat, input_fn, output_fn, run_id="walkthrough_001")

    stages_seen = {entry["stage"] for entry in state.log_entries}
    assert "stage1_clarify_goal" in stages_seen
    assert "stage2_select_dimensions" in stages_seen
    assert "stage3_draft_evaluator" in stages_seen
    assert "stage4_sample_judgment" in stages_seen
    assert "stage5_adjust_judge" in stages_seen
    assert "stage6_approve" in stages_seen

    assert state.task_spec is not None
    assert state.task_spec.task_class == "generate"
    assert state.task_spec.output_kind == "open"

    assert len(state.selected_dimensions) == 2
    assert {d.id for d in state.selected_dimensions} == {"char_limit", "keyword_inclusion"}

    assert state.approved is True

    log_path = tmp_path / "logs" / "walkthrough_001.jsonl"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(state.log_entries)


# === LLM 提案フォールバック ===


def test_llm_suggest_fires_on_empty_answer_and_is_validated(tmp_path: Path) -> None:
    config = DialogConfig(
        log_dir=tmp_path / "logs",
        timestamp_fn=lambda: "2026-06-20T12:00:00Z",
    )

    suggestions = iter([
        {"suggestion": "ILLEGAL_VALUE"},
        {"suggestion": "open"},
        {"suggestion": "free_text"},
        {"suggestion": "auto_domain"},
    ])

    def fake_json_chat(messages: list[dict]) -> dict:
        return next(suggestions)

    answers = [
        "目的テスト",
        "",
        "generate",
        "",
        "",
        "",
        "",
        "",
        "",
        "input_x:target",
        "out:o_v1",
        "",
    ]
    input_fn, _ = _scripted_input(answers)
    output_fn, _ = _collect_output()
    state = stage1_clarify_goal(DialogState(), config, fake_json_chat, input_fn, output_fn)
    assert state.task_spec is not None
    assert state.task_spec.task_class == "generate"
    assert state.task_spec.output_kind == "open"
    assert state.task_spec.input_modality == "free_text"
    assert state.task_spec.domain == "auto_domain"


def test_llm_suggest_disabled_when_json_chat_fn_is_none(tmp_path: Path) -> None:
    config = DialogConfig(log_dir=tmp_path / "logs")
    answers = [
        "目的",
        "",
        "open",
        "doc",
        "x",
        "",
        "",
        "",
    ]
    input_fn, _ = _scripted_input(answers)
    output_fn, _ = _collect_output()
    with pytest.raises(ValueError, match="許可されない値"):
        stage1_clarify_goal(DialogState(), config, None, input_fn, output_fn)


# === EvalDimension dataclass のヘルパー ===


def test_eval_dimension_matches() -> None:
    d = EvalDimension(
        id="x",
        label="X",
        type="deterministic",
        applicable_task_classes=("generate",),
        applicable_output_kinds=("open",),
    )
    assert d.matches("generate", "open") is True
    assert d.matches("generate", "closed") is False
    assert d.matches("detect", "open") is False


# === DialogConfig のデフォルトが repo 内 YAML を指す ===


def test_dialog_config_defaults_point_to_repo_yaml() -> None:
    """DialogConfig のデフォルト questions_root / dimensions_root が repo 内 YAML を指す."""
    config = DialogConfig(log_dir=Path("/tmp/dummy"))
    assert config.questions_root == DEFAULT_QUESTIONS_ROOT
    assert config.dimensions_root == DEFAULT_DIMENSIONS_ROOT
    # 実在性確認
    assert (config.questions_root / "_common").is_dir()
    assert (config.dimensions_root / "_common").is_dir()
