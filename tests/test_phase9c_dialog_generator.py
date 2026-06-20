"""Phase 9c (2026-06-21): 対話ベース評価器生成の構造確認.

設計 phase9_design §3.3 / §4.2 9c ゲートに対応.

確認項目:
- パラメータ抽出 (extract_dimension_parameters) が EvalDimension.parameters を
  動的 Q として展開
- LLM judge 系のとき判定基準 (criteria) を別途取得
- LLM 提案が空回答時に発火
- 重み付け (equal / custom) が確定
- 厳しさ guardrails が統合される
- implementation_source が template + params で合成され、構文として valid
- _infer_evaluator_type が軸構成から正しく推論
- EvaluatorDraft → EvaluatorSpec 変換
- stage3_draft_evaluator が dialog 経由で完走 (yes/no 両分岐)
- stage3 yaml が _common にロードされる
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tsumiki.eval.core.dialog_generator import (
    DimensionParameters,
    build_evaluator_draft,
    build_implementation_source,
    draft_to_evaluator_spec,
    extract_dimension_parameters,
    resolve_strictness_guardrails,
    resolve_weights,
)
from tsumiki.goal.dialog import (
    DialogConfig,
    DialogState,
    stage1_clarify_goal,
    stage2_select_dimensions,
    stage3_draft_evaluator,
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


# === stage3 YAML の存在 ===


def test_stage3_yaml_loaded_from_common() -> None:
    stage = load_dialog_questions(QUESTIONS_ROOT, "stage3")
    ids = {q.id for q in stage.questions}
    assert ids == {"weights_mode", "strictness", "evaluator_draft_confirm"}


def test_stage3_strictness_allowed_values() -> None:
    stage = load_dialog_questions(QUESTIONS_ROOT, "stage3")
    q = next(q for q in stage.questions if q.id == "strictness")
    assert set(q.allowed_values) == {"strict", "lenient", "balanced"}


def test_stage3_weights_mode_allowed_values() -> None:
    stage = load_dialog_questions(QUESTIONS_ROOT, "stage3")
    q = next(q for q in stage.questions if q.id == "weights_mode")
    assert set(q.allowed_values) == {"equal", "custom"}


# === extract_dimension_parameters ===


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
        parameters=(
            EvalDimensionParameter(name="criteria", type="str", required=True),
        ),
        prompt_template="基準: {criteria}\n対象: {output}",
        guardrails=("panel_3",),
    )


def test_extract_parameters_for_deterministic_dimension() -> None:
    dim = _make_char_limit_dim()
    input_fn, _ = _scripted_input(["", "100"])  # min_chars 空 (default 採用), max_chars 100
    output_fn, _ = _collect_output()
    params = extract_dimension_parameters(dim, "目的x", input_fn, output_fn, None)
    assert params.dimension_id == "char_limit"
    assert params.param_values == {"min_chars": 0, "max_chars": 100}
    assert params.judge_criteria == ""


def test_extract_parameters_required_without_default_raises() -> None:
    dim = _make_char_limit_dim()
    input_fn, _ = _scripted_input(["0", ""])  # max_chars 空 (required かつ default なし)
    output_fn, _ = _collect_output()
    with pytest.raises(ValueError, match="必須"):
        extract_dimension_parameters(dim, "目的", input_fn, output_fn, None)


def test_extract_parameters_for_judge_dimension_with_user_criteria() -> None:
    dim = _make_judge_panel_dim()
    input_fn, _ = _scripted_input(["ブランドガイドライン遵守", "ユーザー入力の基準"])
    output_fn, _ = _collect_output()
    params = extract_dimension_parameters(dim, "目的", input_fn, output_fn, None)
    assert params.param_values == {"criteria": "ブランドガイドライン遵守"}
    assert params.judge_criteria == "ユーザー入力の基準"


def test_extract_parameters_for_judge_with_llm_suggestion() -> None:
    dim = _make_judge_panel_dim()
    # criteria param → "x", judge_criteria 空 → LLM 提案 → edit 空 (採用)
    input_fn, _ = _scripted_input(["x", "", ""])
    output_fn, _ = _collect_output()

    def fake_json_chat(messages: list[dict]) -> dict:
        return {"criteria": "LLM が提案した基準"}

    params = extract_dimension_parameters(dim, "目的", input_fn, output_fn, fake_json_chat)
    assert params.judge_criteria == "LLM が提案した基準"


# === resolve_weights ===


def test_resolve_weights_equal() -> None:
    dims = (
        DimensionParameters(dimension_id="a", param_values={}),
        DimensionParameters(dimension_id="b", param_values={}),
    )
    input_fn, _ = _scripted_input([])
    output_fn, _ = _collect_output()
    weights = resolve_weights(dims, "equal", input_fn, output_fn)
    assert weights == {"a": 0.5, "b": 0.5}


def test_resolve_weights_custom_normalized() -> None:
    dims = (
        DimensionParameters(dimension_id="a", param_values={}),
        DimensionParameters(dimension_id="b", param_values={}),
    )
    input_fn, _ = _scripted_input(["2.0", "1.0"])  # 合計 3.0 → 正規化で 0.667 / 0.333
    output_fn, _ = _collect_output()
    weights = resolve_weights(dims, "custom", input_fn, output_fn)
    assert abs(weights["a"] - 2 / 3) < 1e-6
    assert abs(weights["b"] - 1 / 3) < 1e-6


def test_resolve_weights_zero_total_raises() -> None:
    dims = (DimensionParameters(dimension_id="a", param_values={}),)
    input_fn, _ = _scripted_input(["0"])
    output_fn, _ = _collect_output()
    with pytest.raises(ValueError, match="0 以下"):
        resolve_weights(dims, "custom", input_fn, output_fn)


# === resolve_strictness_guardrails ===


def test_strictness_guardrails_aggregates_per_dimension() -> None:
    judge = _make_judge_panel_dim()
    char_limit = _make_char_limit_dim()
    dim_specs = {"llm_judge_panel": judge, "char_limit": char_limit}
    dims = (
        DimensionParameters(dimension_id="llm_judge_panel", param_values={}),
        DimensionParameters(dimension_id="char_limit", param_values={}),
    )
    guardrails = resolve_strictness_guardrails("strict", dims, dim_specs)
    assert "strictness:strict" in guardrails
    assert "panel_3" in guardrails


# === implementation 合成 ===


def test_build_implementation_for_deterministic_compiles() -> None:
    dim = _make_char_limit_dim()
    dim_specs = {"char_limit": dim}
    dims = (DimensionParameters(dimension_id="char_limit", param_values={"min_chars": 0, "max_chars": 50}),)
    source = build_implementation_source(dims, dim_specs, {"char_limit": 1.0}, "balanced")
    # 構文として valid
    compile(source, "<generated>", "exec")
    # source に埋め込まれた値が含まれている
    assert "max_chars=50" in source or "max_chars': 50" in source or "balanced" in source
    assert "evaluate(payload" in source


def test_build_implementation_for_judge_includes_prompt() -> None:
    dim = _make_judge_panel_dim()
    dim_specs = {"llm_judge_panel": dim}
    dims = (
        DimensionParameters(
            dimension_id="llm_judge_panel",
            param_values={"criteria": "X"},
            judge_criteria="ブランドトーン遵守",
        ),
    )
    source = build_implementation_source(dims, dim_specs, {"llm_judge_panel": 1.0}, "strict")
    compile(source, "<generated>", "exec")
    assert "ブランドトーン遵守" in source
    assert "strict" in source


def test_build_implementation_missing_param_raises() -> None:
    """implementation_template に未指定のパラメータが残っていると build 失敗."""
    dim = EvalDimension(
        id="x",
        label="X",
        type="deterministic",
        applicable_task_classes=("generate",),
        applicable_output_kinds=("open",),
        implementation_template="def evaluate(o, k={kkk}): return {{'score': 1.0}}",
    )
    dim_specs = {"x": dim}
    dims = (DimensionParameters(dimension_id="x", param_values={}),)
    with pytest.raises(ValueError, match="未指定パラメータ"):
        build_implementation_source(dims, dim_specs, {"x": 1.0}, "balanced")


# === EvaluatorDraft 構築 + Spec 変換 ===


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


def test_build_draft_then_to_spec_for_deterministic() -> None:
    task = _make_task_spec()
    dim = _make_char_limit_dim()
    dim_specs = {"char_limit": dim}
    dims = (DimensionParameters(dimension_id="char_limit", param_values={"min_chars": 1, "max_chars": 200}),)
    draft = build_evaluator_draft(task, dims, dim_specs, {"char_limit": 1.0}, "balanced")
    assert draft.evaluator_type == "deterministic"
    spec = draft_to_evaluator_spec(draft, evaluator_id="x_v1", generated_at="2026-06-21", approved_by="auto")
    assert spec.id == "x_v1"
    assert spec.output_kind == "open"
    assert spec.task_class == "generate"
    assert spec.is_approved() is True
    assert "char_limit" in spec.sources
    assert "score_char_limit" in spec.output_metrics


def test_build_draft_infers_hybrid_for_mixed_types() -> None:
    task = _make_task_spec()
    char = _make_char_limit_dim()
    judge = _make_judge_panel_dim()
    dim_specs = {"char_limit": char, "llm_judge_panel": judge}
    dims = (
        DimensionParameters(dimension_id="char_limit", param_values={"min_chars": 0, "max_chars": 50}),
        DimensionParameters(
            dimension_id="llm_judge_panel",
            param_values={"criteria": "X"},
            judge_criteria="X",
        ),
    )
    draft = build_evaluator_draft(task, dims, dim_specs, {"char_limit": 0.5, "llm_judge_panel": 0.5}, "balanced")
    assert draft.evaluator_type == "hybrid"


def test_build_draft_infers_llm_judge_for_only_judge_types() -> None:
    task = _make_task_spec()
    judge = _make_judge_panel_dim()
    dim_specs = {"llm_judge_panel": judge}
    dims = (
        DimensionParameters(
            dimension_id="llm_judge_panel",
            param_values={"criteria": "X"},
            judge_criteria="X",
        ),
    )
    draft = build_evaluator_draft(task, dims, dim_specs, {"llm_judge_panel": 1.0}, "balanced")
    assert draft.evaluator_type == "llm_judge"


# === stage3_draft_evaluator 完走 ===


def test_stage3_full_flow_with_confirm_yes(tmp_path: Path) -> None:
    """stage1 → stage2 → stage3 を yes 確認で通す."""
    config = DialogConfig(
        log_dir=tmp_path / "logs",
        timestamp_fn=lambda: "2026-06-21T12:00:00Z",
    )
    answers = [
        # stage1 Q1〜Q8
        "ビーガン向けプロテインバーを訴求",
        "generate",
        "open",
        "free_text",
        "marketing_post",
        "",
        "post:p_v1",
        "",
        # stage2 Q9: 軸選択
        "char_limit,keyword_inclusion",
        # stage3: dim parameters
        # char_limit: min_chars (default 0 採用), max_chars
        "",   # min_chars
        "150",  # max_chars
        # keyword_inclusion: required_keywords, forbidden_keywords (default 採用)
        "新発売,ビーガン",
        "",
        # Q11 weights_mode
        "equal",
        # Q12 strictness
        "balanced",
        # Q13 confirm
        "yes",
    ]
    input_fn, _ = _scripted_input(answers)
    output_fn, _ = _collect_output()

    state = stage1_clarify_goal(DialogState(), config, None, input_fn, output_fn)
    state = stage2_select_dimensions(state, config, input_fn, output_fn)
    state = stage3_draft_evaluator(state, config, None, input_fn, output_fn)

    assert state.eval_spec_draft is not None
    draft = state.eval_spec_draft
    assert {d.dimension_id for d in draft.dimensions} == {"char_limit", "keyword_inclusion"}
    assert draft.strictness == "balanced"
    assert sum(draft.weights.values()) == pytest.approx(1.0)
    assert draft.evaluator_type == "deterministic"
    # 生成コードが syntactically valid
    compile(draft.implementation_source, "<generated>", "exec")


def test_stage3_with_confirm_no_keeps_draft_none(tmp_path: Path) -> None:
    """確認 no で draft が None のまま残る (stage2 への差し戻しメッセージ)."""
    config = DialogConfig(
        log_dir=tmp_path / "logs",
        timestamp_fn=lambda: "2026-06-21T12:00:00Z",
    )
    answers = [
        "目的",
        "generate",
        "open",
        "free_text",
        "x_domain",
        "",
        "result:r_v1",
        "",
        "char_limit",
        # stage3: char_limit params
        "",
        "100",
        # weights_mode / strictness / confirm
        "equal",
        "lenient",
        "no",
    ]
    input_fn, _ = _scripted_input(answers)
    output_fn, msgs = _collect_output()

    state = stage1_clarify_goal(DialogState(), config, None, input_fn, output_fn)
    state = stage2_select_dimensions(state, config, input_fn, output_fn)
    state = stage3_draft_evaluator(state, config, None, input_fn, output_fn)

    assert state.eval_spec_draft is None
    assert any("差し戻し" in m for m in msgs)


def test_stage3_custom_weights_normalize(tmp_path: Path) -> None:
    config = DialogConfig(
        log_dir=tmp_path / "logs",
        timestamp_fn=lambda: "2026-06-21T12:00:00Z",
    )
    answers = [
        "目的",
        "generate",
        "open",
        "free_text",
        "x",
        "",
        "r:r_v1",
        "",
        "char_limit,keyword_inclusion",
        "",      # char_limit min_chars
        "100",   # char_limit max_chars
        "kw1",   # keyword required
        "",      # keyword forbidden (default)
        "custom",
        "2.0",   # char_limit weight
        "1.0",   # keyword_inclusion weight
        "strict",
        "yes",
    ]
    input_fn, _ = _scripted_input(answers)
    output_fn, _ = _collect_output()

    state = stage1_clarify_goal(DialogState(), config, None, input_fn, output_fn)
    state = stage2_select_dimensions(state, config, input_fn, output_fn)
    state = stage3_draft_evaluator(state, config, None, input_fn, output_fn)

    assert state.eval_spec_draft is not None
    draft = state.eval_spec_draft
    assert abs(draft.weights["char_limit"] - 2 / 3) < 1e-6
    assert abs(draft.weights["keyword_inclusion"] - 1 / 3) < 1e-6
    assert "strictness:strict" in draft.guardrails


def test_stage3_without_selected_dimensions_skips(tmp_path: Path) -> None:
    """軸が未選択なら stage3 はスキップ."""
    config = DialogConfig(log_dir=tmp_path / "logs")
    state = DialogState()
    state.task_spec = _make_task_spec()
    state.selected_dimensions = ()
    input_fn, _ = _scripted_input([])
    output_fn, msgs = _collect_output()
    state = stage3_draft_evaluator(state, config, None, input_fn, output_fn)
    assert state.eval_spec_draft is None
    assert any("スキップ" in m for m in msgs)


def test_stage3_without_task_spec_raises(tmp_path: Path) -> None:
    config = DialogConfig(log_dir=tmp_path / "logs")
    state = DialogState()
    input_fn, _ = _scripted_input([])
    output_fn, _ = _collect_output()
    with pytest.raises(RuntimeError, match="stage1"):
        stage3_draft_evaluator(state, config, None, input_fn, output_fn)
