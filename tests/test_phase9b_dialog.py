"""Phase 9b: 対話 REPL + 評価軸 loader の構造確認.

設計 phase9_design §3.2 / §4.2 9b ゲートに対応.

確認項目:
- eval_dimensions loader が _common/ をロードする
- domain 指定で _common + <domain>/ を merge できる
- filter_applicable が task_class + output_kind で正しく絞る
- 構造化質問 Q1〜Q10 が定義されている
- 6 stage を mock LLM + scripted input で完走する
- 対話ログが JSONL で persist される
- LLM 提案が空回答時に発火し、選択肢チェックが効く
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tsumiki.goal.dialog import (
    QUESTIONS_APPROVE,
    QUESTIONS_DIMENSIONS,
    QUESTIONS_TASK_SPEC,
    DialogConfig,
    DialogState,
    run_dialog,
    stage1_clarify_goal,
    stage2_select_dimensions,
    stage6_approve,
)
from tsumiki.knowledge.schemas.eval_dimensions import (
    EvalDimension,
    filter_applicable,
    load_eval_dimensions,
)

DIMENSIONS_ROOT = Path("src/tsumiki/knowledge/schemas/eval_dimensions")


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

    # generate + open: char_limit, keyword_inclusion, llm_judge_panel, llm_judge_pairwise が候補
    applicable = filter_applicable(dims, task_class="generate", output_kind="open")
    ids = {d.id for d in applicable}
    assert "char_limit" in ids
    assert "keyword_inclusion" in ids
    assert "llm_judge_panel" in ids
    # format_validity は applicable_output_kinds=[closed, semi_open] なので open には乗らない
    assert "format_validity" not in ids

    # detect + closed: char_limit (closed 対応) は乗らない (applicable_task_classes に detect なし)
    applicable_detect = filter_applicable(dims, task_class="detect", output_kind="closed")
    assert all(d.id != "char_limit" for d in applicable_detect)


def test_missing_common_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_eval_dimensions(tmp_path)


# === 構造化質問の定義 ===


def test_questions_task_spec_count_and_ids() -> None:
    """Q1〜Q8 が定義されている."""
    assert len(QUESTIONS_TASK_SPEC) == 8
    ids = [q.id for q in QUESTIONS_TASK_SPEC]
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


def test_questions_task_spec_allowed_values_match_literals() -> None:
    """task_class / output_kind / input_modality の allowed_values が Literal と一致."""
    q_task = next(q for q in QUESTIONS_TASK_SPEC if q.id == "task_class")
    assert "generate" in q_task.allowed_values
    assert "detect" in q_task.allowed_values  # 既存も維持

    q_out = next(q for q in QUESTIONS_TASK_SPEC if q.id == "output_kind")
    assert set(q_out.allowed_values) == {"closed", "semi_open", "open"}

    q_inm = next(q for q in QUESTIONS_TASK_SPEC if q.id == "input_modality")
    assert set(q_inm.allowed_values) == {"doc", "free_text", "structured", "mixed", "none"}


def test_questions_dimensions_one_question() -> None:
    assert len(QUESTIONS_DIMENSIONS) == 1
    assert QUESTIONS_DIMENSIONS[0].id == "selected_dimensions"


def test_questions_approve_one_yes_no() -> None:
    assert len(QUESTIONS_APPROVE) == 1
    assert QUESTIONS_APPROVE[0].expected_type == "yes_no"


# === scripted I/O ヘルパ ===


def _scripted_input(answers: list[str]) -> tuple[Iterator[str], list[str]]:
    """順次回答を返す iterator + 採用ログ."""
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
    """messages を list に蓄積."""
    msgs: list[str] = []

    def fn(msg: str) -> None:
        msgs.append(msg)

    return fn, msgs  # type: ignore[return-value]


# === stage 1 単体 ===


def test_stage1_constructs_task_spec_from_8_answers(tmp_path: Path) -> None:
    config = DialogConfig(
        log_dir=tmp_path / "logs",
        dimensions_root=DIMENSIONS_ROOT,
        timestamp_fn=lambda: "2026-06-20T12:00:00Z",
    )
    answers = [
        "ビーガン向けプロテインバーの 9 月発売を訴求したい",  # raw_goal
        "generate",                                              # task_class
        "open",                                                  # output_kind
        "free_text",                                             # input_modality
        "marketing_post",                                        # domain
        "intent_text:intent",                                    # input_roles_csv
        "post_text:instagram_post_v1",                           # outputs_csv
        "knowledge/skills/marketing_post",                       # knowledge_catalog_path
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
    config = DialogConfig(log_dir=tmp_path / "logs", dimensions_root=DIMENSIONS_ROOT)
    answers = [
        "目的",
        "INVALID_TASK_CLASS",  # 不正な task_class
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
    config = DialogConfig(log_dir=tmp_path / "logs", dimensions_root=DIMENSIONS_ROOT)
    state = DialogState()
    # 必要な task_spec を直接 set
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
    output_fn, msgs = _collect_output()

    state = stage2_select_dimensions(state, config, input_fn, output_fn)
    assert len(state.selected_dimensions) == 2
    assert {d.id for d in state.selected_dimensions} == {"char_limit", "llm_judge_panel"}


def test_stage2_unknown_dimension_raises(tmp_path: Path) -> None:
    config = DialogConfig(log_dir=tmp_path / "logs", dimensions_root=DIMENSIONS_ROOT)
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
        dimensions_root=DIMENSIONS_ROOT,
        timestamp_fn=lambda: "2026-06-20T12:00:00Z",
    )
    input_fn, _ = _scripted_input(["yes"])
    output_fn, _ = _collect_output()
    state = stage6_approve(DialogState(), config, input_fn, output_fn)
    assert state.approved is True
    assert state.approved_by.startswith("user_dialog_2026-06-20T12:00:00Z")


def test_stage6_approve_no(tmp_path: Path) -> None:
    config = DialogConfig(log_dir=tmp_path / "logs", dimensions_root=DIMENSIONS_ROOT)
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
        dimensions_root=DIMENSIONS_ROOT,
        timestamp_fn=lambda: "2026-06-20T12:00:00Z",
    )
    # 順序: Q1〜Q8 (stage1), Q9 (stage2), Q10 (stage6)
    answers = [
        "目的: テスト",                                  # raw_goal
        "generate",                                       # task_class
        "open",                                           # output_kind
        "free_text",                                      # input_modality
        "test_domain",                                    # domain
        "",                                               # input_roles_csv (空)
        "result:result_v1",                               # outputs_csv
        "",                                               # knowledge_catalog_path (空)
        "char_limit,keyword_inclusion",                   # stage2 selected_dimensions
        "yes",                                            # stage6 approve
    ]
    input_fn, _ = _scripted_input(answers)
    output_fn, msgs = _collect_output()

    def fake_json_chat(messages: list[dict]) -> dict:
        return {"suggestion": ""}

    state = run_dialog(config, fake_json_chat, input_fn, output_fn, run_id="walkthrough_001")

    # 各 stage 通過
    stages_seen = {entry["stage"] for entry in state.log_entries}
    assert "stage1_clarify_goal" in stages_seen
    assert "stage2_select_dimensions" in stages_seen
    assert "stage3_draft_evaluator" in stages_seen
    assert "stage4_sample_judgment" in stages_seen
    assert "stage5_adjust_judge" in stages_seen
    assert "stage6_approve" in stages_seen

    # task_spec 確定
    assert state.task_spec is not None
    assert state.task_spec.task_class == "generate"
    assert state.task_spec.output_kind == "open"
    assert state.task_spec.input_modality == "free_text"

    # 評価軸選択
    assert len(state.selected_dimensions) == 2
    assert {d.id for d in state.selected_dimensions} == {"char_limit", "keyword_inclusion"}

    # 承認
    assert state.approved is True
    assert state.approved_by.startswith("user_dialog_2026-06-20T12:00:00Z")

    # ログ JSONL が persist
    log_path = tmp_path / "logs" / "walkthrough_001.jsonl"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(state.log_entries)


# === LLM 提案フォールバック ===


def test_llm_suggest_fires_on_empty_answer_and_is_validated(tmp_path: Path) -> None:
    """空回答時に LLM 提案を発火させ、許可されない提案は無視される."""
    config = DialogConfig(
        log_dir=tmp_path / "logs",
        dimensions_root=DIMENSIONS_ROOT,
        timestamp_fn=lambda: "2026-06-20T12:00:00Z",
    )

    suggestions = iter([
        # task_class: 不正な提案 → 採用されず、ユーザーの再入力を要求
        {"suggestion": "ILLEGAL_VALUE"},
        # output_kind: 妥当な提案
        {"suggestion": "open"},
        # input_modality: 妥当な提案
        {"suggestion": "free_text"},
        # domain: 提案受領
        {"suggestion": "auto_domain"},
    ])

    def fake_json_chat(messages: list[dict]) -> dict:
        return next(suggestions)

    answers = [
        "目的テスト",       # Q1 raw_goal
        "",                # Q2 task_class: 空 → LLM 提案 (ILLEGAL)
        "generate",        # 再入力 (LLM 提案が無効だったため)
        "",                # Q3 output_kind: 空 → LLM 提案 "open"
        "",                # 提案採用 (Enter)
        "",                # Q4 input_modality: 空 → LLM 提案 "free_text"
        "",                # 提案採用
        "",                # Q5 domain: 空 → LLM 提案 "auto_domain"
        "",                # 提案採用
        "input_x:target",  # Q6
        "out:o_v1",        # Q7
        "",                # Q8
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
    """json_chat_fn=None なら LLM 提案を使わず、空回答はそのまま空のまま検証で失敗する."""
    config = DialogConfig(log_dir=tmp_path / "logs", dimensions_root=DIMENSIONS_ROOT)
    answers = [
        "目的",
        "",       # task_class 空, 提案なし → 検証 NG
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
