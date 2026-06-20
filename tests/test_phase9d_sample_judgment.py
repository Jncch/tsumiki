"""Phase 9d (2026-06-21): サンプル提示 + 判定一致確認 + judge 調整の構造確認.

設計 phase9_design §3.4-3.5 / §4.2 9d ゲートに対応.

確認項目:
- generate_samples が json_chat_fn を呼んで Sample tuple を返す (失敗時は空)
- judge_samples_with_draft が deterministic 軸で per_dim_scores を計算
- LLM judge 軸は pending_dim_ids に積まれる
- compute_disagreements が user/system 食い違いを抽出
- collect_judge_dimension_ids が LLM judge 系のみ拾う
- suggest_criteria_revision が LLM 提案を返す
- apply_criteria_revisions が criteria を更新した EvaluatorDraft を返す
- stage4 / stage5 yaml ロード
- stage4 完走 (3 件サンプル, system vs user 判定一致 & 不一致)
- stage5 完走 (yes 経路 / no 経路 / judge 軸無し)
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from tsumiki.eval.core.dialog_generator import (
    DimensionParameters,
    build_evaluator_draft,
)
from tsumiki.eval.core.judge_adjuster import (
    apply_criteria_revisions,
    collect_judge_dimension_ids,
    suggest_criteria_revision,
)
from tsumiki.eval.core.sample_judgment import (
    Disagreement,
    Sample,
    SystemJudgment,
    UserJudgment,
    compute_disagreements,
    generate_samples,
    judge_samples_with_draft,
)
from tsumiki.goal.dialog import (
    DialogConfig,
    DialogState,
    stage1_clarify_goal,
    stage2_select_dimensions,
    stage3_draft_evaluator,
    stage4_sample_judgment,
    stage5_adjust_judge,
)
from tsumiki.goal.specs import KnowledgeSource, TaskSpec
from tsumiki.knowledge.schemas.dialog_questions import load_dialog_questions
from tsumiki.knowledge.schemas.eval_dimensions import (
    EvalDimension,
    EvalDimensionParameter,
)

QUESTIONS_ROOT = Path("src/tsumiki/knowledge/schemas/dialog_questions")
DIMENSIONS_ROOT = Path("src/tsumiki/knowledge/schemas/eval_dimensions")


# === scripted I/O ===


def _scripted_input(answers: list[str]) -> tuple[Iterator[str], list[str]]:
    log: list[str] = []
    it = iter(answers)

    def fn(prompt: str) -> str:
        try:
            val = next(it)
        except StopIteration:
            raise RuntimeError(f"想定外の質問: {prompt}") from None
        log.append(f"{prompt} -> {val}")
        return val

    return fn, log  # type: ignore[return-value]


def _collect_output() -> tuple[list[str], list[str]]:
    msgs: list[str] = []

    def fn(msg: str) -> None:
        msgs.append(msg)

    return fn, msgs  # type: ignore[return-value]


# === Helper builders ===


def _make_char_limit_dim() -> EvalDimension:
    return EvalDimension(
        id="char_limit",
        label="文字数制限",
        type="deterministic",
        applicable_task_classes=("generate",),
        applicable_output_kinds=("open",),
        parameters=(
            EvalDimensionParameter(name="min_chars", type="int", default=0),
            EvalDimensionParameter(name="max_chars", type="int", required=True),
        ),
        implementation_template=(
            "def evaluate(output, min_chars={min_chars}, max_chars={max_chars}):\n"
            "    n = len(output)\n"
            "    return {{'score': 1.0 if min_chars <= n <= max_chars else 0.0}}\n"
        ),
    )


def _make_judge_panel_dim() -> EvalDimension:
    return EvalDimension(
        id="llm_judge_panel",
        label="LLM 複数批評パネル",
        type="llm_judge_panel",
        applicable_task_classes=("generate",),
        applicable_output_kinds=("open",),
        parameters=(EvalDimensionParameter(name="criteria", type="str", required=True),),
        prompt_template="基準: {criteria}\n対象: {output}",
        guardrails=("panel_3",),
    )


def _make_task_spec() -> TaskSpec:
    return TaskSpec(
        task_class="generate",
        domain="marketing_post",
        input_roles=(),
        knowledge=KnowledgeSource(source_type="existing", catalog_path="x"),
        outputs=(),
        output_kind="open",
        input_modality="free_text",
    )


# === stage4 / stage5 YAML 存在 ===


def test_stage4_yaml_loaded() -> None:
    stage = load_dialog_questions(QUESTIONS_ROOT, "stage4")
    assert any(q.id == "user_passed" for q in stage.questions)


def test_stage5_yaml_loaded() -> None:
    stage = load_dialog_questions(QUESTIONS_ROOT, "stage5")
    ids = {q.id for q in stage.questions}
    assert ids == {"adjust_request", "dimensions_to_adjust", "criteria_revision"}


# === generate_samples ===


def test_generate_samples_via_json_chat_fn() -> None:
    spec = _make_task_spec()

    def fake_json_chat(messages: list[dict]) -> dict:
        return {
            "samples": [
                {"id": "s1", "output": "良い例 100 文字程度のテキスト"},
                {"id": "s2", "output": "短"},
            ]
        }

    samples = generate_samples(spec, 2, fake_json_chat)
    assert len(samples) == 2
    assert samples[0].id == "s1"
    assert "良い" in samples[0].output


def test_generate_samples_handles_chat_failure() -> None:
    spec = _make_task_spec()

    def broken_chat(messages: list[dict]) -> dict:
        raise RuntimeError("LLM down")

    samples = generate_samples(spec, 3, broken_chat)
    assert samples == ()


# === judge_samples_with_draft ===


def test_judge_with_deterministic_dim_computes_scores() -> None:
    spec = _make_task_spec()
    char = _make_char_limit_dim()
    dim_specs = {"char_limit": char}
    dims = (DimensionParameters(dimension_id="char_limit", param_values={"min_chars": 5, "max_chars": 50}),)
    draft = build_evaluator_draft(spec, dims, dim_specs, {"char_limit": 1.0}, "balanced")

    samples = (
        Sample(id="ok", output="ちょうど良い長さの 20 文字くらいのテキスト"),  # 約 20 字 → PASS
        Sample(id="long", output="x" * 200),                                   # 200 字 → FAIL
        Sample(id="empty", output=""),                                          # 0 字 → FAIL
    )
    judgments = judge_samples_with_draft(samples, draft, dim_specs)
    by_id = {j.sample_id: j for j in judgments}
    assert by_id["ok"].passed is True
    assert by_id["long"].passed is False
    assert by_id["empty"].passed is False
    assert by_id["ok"].pending_dim_ids == ()


def test_judge_marks_llm_judge_dim_pending() -> None:
    spec = _make_task_spec()
    panel = _make_judge_panel_dim()
    dim_specs = {"llm_judge_panel": panel}
    dims = (
        DimensionParameters(
            dimension_id="llm_judge_panel",
            param_values={"criteria": "X"},
            judge_criteria="X",
        ),
    )
    draft = build_evaluator_draft(spec, dims, dim_specs, {"llm_judge_panel": 1.0}, "balanced")
    samples = (Sample(id="s1", output="サンプル"),)
    j = judge_samples_with_draft(samples, draft, dim_specs)[0]
    assert "llm_judge_panel" in j.pending_dim_ids
    assert j.score == 0.0
    assert j.passed is False


def test_judge_with_hybrid_skips_pending_dim_in_average() -> None:
    """deterministic + llm_judge 混在で deterministic 部分のみで判定."""
    spec = _make_task_spec()
    char = _make_char_limit_dim()
    panel = _make_judge_panel_dim()
    dim_specs = {"char_limit": char, "llm_judge_panel": panel}
    dims = (
        DimensionParameters(dimension_id="char_limit", param_values={"min_chars": 0, "max_chars": 100}),
        DimensionParameters(
            dimension_id="llm_judge_panel",
            param_values={"criteria": "X"},
            judge_criteria="X",
        ),
    )
    draft = build_evaluator_draft(spec, dims, dim_specs, {"char_limit": 0.5, "llm_judge_panel": 0.5}, "lenient")
    sample = Sample(id="s1", output="50 字程度のテキスト サンプル " * 1)
    j = judge_samples_with_draft((sample,), draft, dim_specs)[0]
    assert "llm_judge_panel" in j.pending_dim_ids
    assert j.score == 1.0  # deterministic 部分のみで full score


# === compute_disagreements ===


def test_compute_disagreements_finds_only_mismatches() -> None:
    system = (
        SystemJudgment(sample_id="a", score=1.0, passed=True, per_dim_scores={}, pending_dim_ids=()),
        SystemJudgment(sample_id="b", score=0.0, passed=False, per_dim_scores={}, pending_dim_ids=()),
    )
    user = (
        UserJudgment(sample_id="a", passed=False),  # 不一致
        UserJudgment(sample_id="b", passed=False),  # 一致
    )
    diffs = compute_disagreements(system, user)
    assert len(diffs) == 1
    assert diffs[0].sample_id == "a"


# === judge_adjuster ===


def test_collect_judge_dimension_ids() -> None:
    spec = _make_task_spec()
    char = _make_char_limit_dim()
    panel = _make_judge_panel_dim()
    dim_specs = {"char_limit": char, "llm_judge_panel": panel}
    dims = (
        DimensionParameters(dimension_id="char_limit", param_values={"min_chars": 0, "max_chars": 100}),
        DimensionParameters(
            dimension_id="llm_judge_panel",
            param_values={"criteria": "X"},
            judge_criteria="X",
        ),
    )
    draft = build_evaluator_draft(spec, dims, dim_specs, {"char_limit": 0.5, "llm_judge_panel": 0.5}, "balanced")
    ids = collect_judge_dimension_ids(draft, dim_specs)
    assert ids == ("llm_judge_panel",)


def test_suggest_criteria_revision_returns_llm_proposal() -> None:
    panel = _make_judge_panel_dim()

    def fake_chat(messages: list[dict]) -> dict:
        return {"criteria": "改善された基準"}

    diffs = (
        Disagreement(sample_id="a", system_passed=True, user_passed=False, pending_dim_ids=()),
    )
    result = suggest_criteria_revision(panel, "古い基準", diffs, "目的x", fake_chat)
    assert result == "改善された基準"


def test_apply_criteria_revisions_updates_draft() -> None:
    spec = _make_task_spec()
    panel = _make_judge_panel_dim()
    dim_specs = {"llm_judge_panel": panel}
    dims = (
        DimensionParameters(
            dimension_id="llm_judge_panel",
            param_values={"criteria": "X"},
            judge_criteria="古い",
        ),
    )
    draft = build_evaluator_draft(spec, dims, dim_specs, {"llm_judge_panel": 1.0}, "balanced")
    new_draft = apply_criteria_revisions(draft, dim_specs, {"llm_judge_panel": "新しい"})
    assert new_draft.dimensions[0].judge_criteria == "新しい"
    # implementation source も再合成されている
    assert "新しい" in new_draft.implementation_source


def test_apply_criteria_revisions_empty_returns_same() -> None:
    spec = _make_task_spec()
    panel = _make_judge_panel_dim()
    dim_specs = {"llm_judge_panel": panel}
    dims = (
        DimensionParameters(
            dimension_id="llm_judge_panel",
            param_values={"criteria": "X"},
            judge_criteria="基準",
        ),
    )
    draft = build_evaluator_draft(spec, dims, dim_specs, {"llm_judge_panel": 1.0}, "balanced")
    new_draft = apply_criteria_revisions(draft, dim_specs, {})
    assert new_draft is draft


# === stage4 完走 ===


def test_stage4_full_flow_with_disagreement(tmp_path: Path) -> None:
    """1〜3 を通して stage4 で system PASS / user FAIL の不一致を捕捉."""
    config = DialogConfig(
        log_dir=tmp_path / "logs",
        timestamp_fn=lambda: "2026-06-21T12:00:00Z",
        sample_count=2,
    )
    answers = [
        # stage1
        "ビーガン向けプロテインバーを訴求", "generate", "open", "free_text",
        "marketing_post",
        "", "post:p_v1", "",
        # stage2
        "char_limit",
        # stage3: char_limit params
        "", "150",
        # weights, strictness, confirm
        "equal", "balanced", "yes",
        # stage4: user judgments (s1=yes, s2=no)
        "yes", "no",
    ]
    input_fn, _ = _scripted_input(answers)
    output_fn, _ = _collect_output()

    def fake_chat(messages: list[dict]) -> dict:
        return {
            "samples": [
                {"id": "s1", "output": "ちょうどいい長さの 30 字くらいのサンプル"},
                {"id": "s2", "output": "短い"},  # char_limit 150 max → s2 は十分短い → PASS
            ]
        }

    state = stage1_clarify_goal(DialogState(), config, None, input_fn, output_fn)
    state = stage2_select_dimensions(state, config, input_fn, output_fn)
    state = stage3_draft_evaluator(state, config, None, input_fn, output_fn)
    state = stage4_sample_judgment(state, config, fake_chat, input_fn, output_fn)

    assert len(state.sample_judgments) == 1
    round_data = state.sample_judgments[0]
    assert len(round_data["samples"]) == 2
    # s2 は system PASS かつ user no → 不一致
    diffs = round_data["disagreements"]
    diff_ids = {d["sample_id"] for d in diffs}
    assert "s2" in diff_ids


def test_stage4_without_chat_fn_skips(tmp_path: Path) -> None:
    config = DialogConfig(log_dir=tmp_path / "logs")
    state = DialogState()
    state.task_spec = _make_task_spec()
    # eval_spec_draft も適当に
    char = _make_char_limit_dim()
    dim_specs = {"char_limit": char}
    state.selected_dimensions = (char,)
    dims = (DimensionParameters(dimension_id="char_limit", param_values={"min_chars": 0, "max_chars": 50}),)
    state.eval_spec_draft = build_evaluator_draft(
        state.task_spec, dims, dim_specs, {"char_limit": 1.0}, "balanced"
    )

    input_fn, _ = _scripted_input([])
    output_fn, msgs = _collect_output()
    state = stage4_sample_judgment(state, config, None, input_fn, output_fn)
    assert state.sample_judgments == []
    assert any("json_chat_fn" in m for m in msgs)


# === stage5 完走 ===


def test_stage5_full_flow_user_chooses_to_adjust(tmp_path: Path) -> None:
    """不一致 + judge 軸あり + Q15 yes → criteria が更新される."""
    config = DialogConfig(
        log_dir=tmp_path / "logs",
        timestamp_fn=lambda: "2026-06-21T12:00:00Z",
    )
    spec = _make_task_spec()
    char = _make_char_limit_dim()
    panel = _make_judge_panel_dim()
    dim_specs = {"char_limit": char, "llm_judge_panel": panel}
    dims = (
        DimensionParameters(dimension_id="char_limit", param_values={"min_chars": 0, "max_chars": 100}),
        DimensionParameters(
            dimension_id="llm_judge_panel",
            param_values={"criteria": "X"},
            judge_criteria="ブランド調和",
        ),
    )
    draft = build_evaluator_draft(spec, dims, dim_specs, {"char_limit": 0.5, "llm_judge_panel": 0.5}, "balanced")

    state = DialogState()
    state.task_spec = spec
    state.selected_dimensions = (char, panel)
    state.eval_spec_draft = draft
    state.sample_judgments = [
        {
            "samples": [{"id": "s1", "output": "x"}],
            "system_judgments": [],
            "user_judgments": [],
            "disagreements": [
                {
                    "sample_id": "s1",
                    "system_passed": True,
                    "user_passed": False,
                    "pending_dim_ids": ["llm_judge_panel"],
                }
            ],
        }
    ]

    # Q15=yes, Q16=all, Q17 で空 (LLM 提案採用)
    answers = ["yes", "all", "", ""]
    input_fn, _ = _scripted_input(answers)
    output_fn, _ = _collect_output()

    def fake_chat(messages: list[dict]) -> dict:
        return {"criteria": "改善された基準"}

    state = stage5_adjust_judge(state, config, fake_chat, input_fn, output_fn)
    revised_dim = state.eval_spec_draft.dimensions[1]
    assert revised_dim.dimension_id == "llm_judge_panel"
    assert revised_dim.judge_criteria == "改善された基準"


def test_stage5_no_disagreement_skips(tmp_path: Path) -> None:
    config = DialogConfig(log_dir=tmp_path / "logs")
    state = DialogState()
    spec = _make_task_spec()
    char = _make_char_limit_dim()
    state.task_spec = spec
    state.selected_dimensions = (char,)
    dim_specs = {"char_limit": char}
    dims = (DimensionParameters(dimension_id="char_limit", param_values={"min_chars": 0, "max_chars": 100}),)
    state.eval_spec_draft = build_evaluator_draft(spec, dims, dim_specs, {"char_limit": 1.0}, "balanced")
    state.sample_judgments = [
        {"samples": [], "system_judgments": [], "user_judgments": [], "disagreements": []}
    ]
    input_fn, _ = _scripted_input([])
    output_fn, msgs = _collect_output()
    state = stage5_adjust_judge(state, config, None, input_fn, output_fn)
    assert any("不一致なし" in m for m in msgs)


def test_stage5_no_judge_dimensions_skips(tmp_path: Path) -> None:
    """LLM judge 軸が無い場合 (deterministic のみ) は Stage 5 をスキップ."""
    config = DialogConfig(log_dir=tmp_path / "logs")
    state = DialogState()
    spec = _make_task_spec()
    char = _make_char_limit_dim()
    state.task_spec = spec
    state.selected_dimensions = (char,)
    dim_specs = {"char_limit": char}
    dims = (DimensionParameters(dimension_id="char_limit", param_values={"min_chars": 0, "max_chars": 100}),)
    state.eval_spec_draft = build_evaluator_draft(spec, dims, dim_specs, {"char_limit": 1.0}, "balanced")
    state.sample_judgments = [
        {
            "samples": [],
            "system_judgments": [],
            "user_judgments": [],
            "disagreements": [
                {
                    "sample_id": "x",
                    "system_passed": True,
                    "user_passed": False,
                    "pending_dim_ids": [],
                }
            ],
        }
    ]
    input_fn, _ = _scripted_input([])
    output_fn, msgs = _collect_output()
    state = stage5_adjust_judge(state, config, None, input_fn, output_fn)
    assert any("LLM judge 軸なし" in m for m in msgs)


def test_stage5_user_declines_adjust(tmp_path: Path) -> None:
    """Q15=no で何も更新されない."""
    config = DialogConfig(log_dir=tmp_path / "logs")
    spec = _make_task_spec()
    panel = _make_judge_panel_dim()
    dim_specs = {"llm_judge_panel": panel}
    dims = (
        DimensionParameters(
            dimension_id="llm_judge_panel",
            param_values={"criteria": "X"},
            judge_criteria="orig",
        ),
    )
    draft = build_evaluator_draft(spec, dims, dim_specs, {"llm_judge_panel": 1.0}, "balanced")
    state = DialogState()
    state.task_spec = spec
    state.selected_dimensions = (panel,)
    state.eval_spec_draft = draft
    state.sample_judgments = [
        {
            "samples": [],
            "system_judgments": [],
            "user_judgments": [],
            "disagreements": [
                {
                    "sample_id": "x",
                    "system_passed": True,
                    "user_passed": False,
                    "pending_dim_ids": ["llm_judge_panel"],
                }
            ],
        }
    ]
    answers = ["no"]
    input_fn, _ = _scripted_input(answers)
    output_fn, _ = _collect_output()
    state = stage5_adjust_judge(state, config, None, input_fn, output_fn)
    # criteria は元のまま
    assert state.eval_spec_draft.dimensions[0].judge_criteria == "orig"
