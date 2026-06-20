"""Phase 9e (2026-06-21): 開放タスク用 runner/e2e.py 拡張の構造確認.

設計 phase9_design §3.5 / §4.2 9e ゲートに対応.

確認項目:
- E2EConfig / E2EResult に Phase 9e フィールドが乗る
- 閉じたタスク (output_kind="closed") は既存パスを通り output_kind="closed" を返す
- 開放タスク (output_kind="open"/"semi_open") は _run_open_ended_e2e に分岐
- evaluator_draft 未設定で開放タスク呼び出すと ValueError
- open_ended_json_chat_fn 未設定で開放タスク呼び出すと ValueError
- knowledge_text の有無で reuse / zerobase が異なるサンプルを生成
- 評価器 implementation を exec して各サンプルの score を集計
- MLflow 記録は副作用なくスキップ可能 (テスト時)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tsumiki.eval.core.dialog_generator import (
    DimensionParameters,
    EvaluatorDraft,
    build_evaluator_draft,
)
from tsumiki.goal.specs import KnowledgeSource, OutputSchema, TaskSpec
from tsumiki.knowledge.schemas.eval_dimensions import (
    EvalDimension,
    EvalDimensionParameter,
)
from tsumiki.runner.e2e import (
    E2EConfig,
    E2EResult,
    _generate_open_ended_samples,
    _run_open_ended_e2e,
    _score_open_ended_samples,
)


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


def _make_open_task_spec() -> TaskSpec:
    return TaskSpec(
        task_class="generate",
        domain="marketing_post",
        input_roles=(),
        knowledge=KnowledgeSource(source_type="existing", catalog_path="x"),
        outputs=(OutputSchema(name="post_text", schema_id="instagram_post_v1"),),
        output_kind="open",
        input_modality="free_text",
        raw_goal="ビーガン向けプロテインバーを訴求",
    )


def _make_draft() -> EvaluatorDraft:
    spec = _make_open_task_spec()
    char = _make_char_limit_dim()
    dim_specs = {"char_limit": char}
    dims = (
        DimensionParameters(
            dimension_id="char_limit",
            param_values={"min_chars": 5, "max_chars": 50},
        ),
    )
    return build_evaluator_draft(
        spec, dims, dim_specs, {"char_limit": 1.0}, "balanced"
    )


# === E2EConfig / E2EResult の Phase 9e フィールド ===


def test_e2e_config_has_open_ended_fields() -> None:
    """新規 default 値が既存呼び出し互換."""
    cfg = E2EConfig(
        goal="x",
        clean_clauses=(),
        seed=42,
        n_synth_per_pattern=1,
        runtime_model="dummy",
        evaluator_root=Path("/tmp/e"),
        parser_chat_fn=lambda *a, **k: {"content": "{}"},  # type: ignore[arg-type]
        generator_chat_fn=lambda *a, **k: {"content": "{}"},  # type: ignore[arg-type]
        runtime_chat_fn=lambda *a, **k: {"content": ""},  # type: ignore[arg-type]
        mlflow_experiment="",
        outcomes_dir=None,
        auto_approve_eval=True,
        generated_at="2026-06-21",
        approved_by="auto",
        modifier_reuse_prompt_version="r",
        modifier_zerobase_prompt_version="z",
        detector_prompt_version="d",
    )
    assert cfg.evaluator_draft is None
    assert cfg.open_ended_sample_count == 8
    assert cfg.open_ended_json_chat_fn is None
    assert cfg.open_ended_knowledge_text is None


def test_e2e_result_default_output_kind_is_closed() -> None:
    spec = _make_open_task_spec()
    res = E2EResult(
        task_spec=spec,
        evaluator_spec=None,
        evaluator_dir=None,
        reused_existing_evaluator=False,
        reuse_metrics={},
        zerobase_metrics={},
        paired_diff=0.0,
    )
    assert res.output_kind == "closed"
    assert res.score_diff is None


# === _generate_open_ended_samples ===


def test_generate_open_ended_samples_with_chat_fn() -> None:
    spec = _make_open_task_spec()

    def fake_chat(messages: list[dict]) -> dict:
        # knowledge_context の有無で違うサンプルを返す
        last = messages[-1]["content"]
        if "knowledge_context" in last:
            return {"samples": [{"id": "r1", "output": "知識ありの長い文" * 3}]}
        return {"samples": [{"id": "z1", "output": "短"}]}

    reuse = _generate_open_ended_samples(
        task_spec=spec,
        knowledge_text="ブランドガイドライン: 健康訴求重視",
        sample_count=1,
        json_chat_fn=fake_chat,
    )
    zerobase = _generate_open_ended_samples(
        task_spec=spec,
        knowledge_text=None,
        sample_count=1,
        json_chat_fn=fake_chat,
    )
    assert reuse[0]["id"] == "r1"
    assert zerobase[0]["id"] == "z1"
    assert reuse[0]["output"] != zerobase[0]["output"]


def test_generate_open_ended_handles_chat_failure() -> None:
    spec = _make_open_task_spec()

    def broken(messages: list[dict]) -> dict:
        raise RuntimeError("LLM down")

    out = _generate_open_ended_samples(
        task_spec=spec, knowledge_text=None, sample_count=3, json_chat_fn=broken
    )
    assert out == ()


# === _score_open_ended_samples ===


def test_score_open_ended_with_deterministic_evaluator() -> None:
    draft = _make_draft()
    samples = (
        {"id": "ok", "output": "ちょうど良い 20 文字くらいのテキスト"},  # PASS
        {"id": "long", "output": "x" * 200},                              # FAIL
        {"id": "empty", "output": ""},                                     # FAIL
    )
    avg, annotated = _score_open_ended_samples(samples, draft.implementation_source)
    assert 0.0 <= avg <= 1.0
    # 1 件は PASS = 1.0
    scores = [a["score"] for a in annotated]
    assert max(scores) == 1.0
    assert min(scores) == 0.0


def test_score_open_ended_handles_empty_samples() -> None:
    draft = _make_draft()
    avg, annotated = _score_open_ended_samples((), draft.implementation_source)
    assert avg == 0.0
    assert annotated == ()


def test_score_open_ended_handles_broken_impl() -> None:
    samples = ({"id": "s", "output": "x"},)
    avg, annotated = _score_open_ended_samples(samples, "raise SyntaxError('x')")
    assert avg == 0.0
    assert annotated == samples


# === _run_open_ended_e2e ===


def _base_cfg(**overrides) -> E2EConfig:
    base = dict(
        goal="ビーガン向けプロテインバーを訴求",
        clean_clauses=(),
        seed=42,
        n_synth_per_pattern=1,
        runtime_model="dummy",
        evaluator_root=Path("/tmp/e"),
        parser_chat_fn=lambda *a, **k: {"content": "{}"},
        generator_chat_fn=lambda *a, **k: {"content": "{}"},
        runtime_chat_fn=lambda *a, **k: {"content": ""},
        mlflow_experiment="",
        outcomes_dir=None,
        auto_approve_eval=True,
        generated_at="2026-06-21",
        approved_by="auto",
        modifier_reuse_prompt_version="r",
        modifier_zerobase_prompt_version="z",
        detector_prompt_version="d",
    )
    base.update(overrides)
    return E2EConfig(**base)  # type: ignore[arg-type]


def test_run_open_ended_e2e_raises_without_draft() -> None:
    spec = _make_open_task_spec()
    cfg = _base_cfg(open_ended_json_chat_fn=lambda *a, **k: {})
    with pytest.raises(ValueError, match="evaluator_draft"):
        _run_open_ended_e2e(cfg, spec)


def test_run_open_ended_e2e_raises_without_json_chat_fn() -> None:
    spec = _make_open_task_spec()
    draft = _make_draft()
    cfg = _base_cfg(evaluator_draft=draft)
    with pytest.raises(ValueError, match="json_chat_fn"):
        _run_open_ended_e2e(cfg, spec)


def test_run_open_ended_e2e_returns_score_diff() -> None:
    """reuse 経路と zerobase 経路で異なるサンプルを返すモックで score_diff を確認."""
    spec = _make_open_task_spec()
    draft = _make_draft()  # max_chars=50

    def fake_chat(messages: list[dict]) -> dict:
        last = messages[-1]["content"]
        # knowledge_context あり → ちょうどいい長さ (PASS) を返す
        if "knowledge_context" in last:
            return {"samples": [
                {"id": "r1", "output": "ちょうど良い 30 字程度のテキストです"},
                {"id": "r2", "output": "また 30 字くらいの文章サンプル"},
            ]}
        # knowledge なし → 短すぎる or 長すぎる (FAIL)
        return {"samples": [
            {"id": "z1", "output": "x"},
            {"id": "z2", "output": "y" * 100},
        ]}

    cfg = _base_cfg(
        evaluator_draft=draft,
        open_ended_json_chat_fn=fake_chat,
        open_ended_knowledge_text="ブランド: 健康訴求",
        open_ended_sample_count=2,
    )
    result = _run_open_ended_e2e(cfg, spec)
    assert result.output_kind == "open"
    assert result.score_diff is not None
    assert result.reuse_score is not None
    assert result.zerobase_score is not None
    # reuse > zerobase が想定
    assert result.score_diff > 0
    assert result.evaluator_spec is None
    assert result.paired_diff is None
    assert result.reuse_samples is not None
    assert len(result.reuse_samples) == 2
