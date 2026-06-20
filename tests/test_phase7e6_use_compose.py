"""Phase 7e-6: runner/e2e.py の use_compose フラグ統合 smoke.

設計書 `phase7e_design.md` §5 (runner/e2e.py との接続).
use_compose=True のとき AgentSquare 探索が補助起動され,
selected_modules / search_score が結果に含まれることを smoke 確認する.

実走 (variant 実行 + Azure / ollama 呼び出し) は重いため, このテストでは
`_run_compose_auxiliary` を直接呼び出す形で smoke 確認に留める.
end-to-end 実走は examples/{nda,iso27001}/run.sh --use-compose (ユーザー実行) で.
"""

from __future__ import annotations

from dataclasses import fields

from tsumiki.goal.specs import (
    EvaluatorSpec,
    KnowledgeSource,
    OutputSchema,
    TaskSpec,
)
from tsumiki.knowledge.schemas.ng_patterns import NGPatternBook
from tsumiki.llm.client import LLMSettings


def _task_spec() -> TaskSpec:
    return TaskSpec(
        task_class="detect_and_modify",
        domain="nda",
        input_roles=(),
        knowledge=KnowledgeSource(source_type="existing", catalog_path="dummy"),
        outputs=(OutputSchema(name="findings", schema_id="ng_findings_v1"),),
        raw_goal="NDA test",
    )


def _eval_spec() -> EvaluatorSpec:
    return EvaluatorSpec(
        id="dummy_eval_v1",
        domain="nda",
        task_class="detect_and_modify",
        type="deterministic",
        input_signature=((), ()),
        output_metrics=("modification_success_rate",),
        implementation="def evaluate(outcomes): return {}",
        test_cases=(),
        guardrails=(),
        sources=(),
        generated_at="2026-06-19",
        approved_by="auto",
    )


def _knowledge() -> NGPatternBook:
    return NGPatternBook(
        version="0.0.0",
        contract_type="nda",
        last_updated="2026-06-19",
        maintainer="test",
        patterns=(),
    )


def _settings() -> LLMSettings:
    return LLMSettings(
        provider="openai_compatible",
        base_url="http://localhost:11434/v1",
        api_key="dummy",
        model="test-model",
        temperature=0.0,
    )


# === E2EConfig / E2EResult に compose フィールドが追加されている ===


def test_e2e_config_has_compose_fields() -> None:
    from tsumiki.runner.e2e import E2EConfig

    field_names = {f.name for f in fields(E2EConfig)}
    assert "use_compose" in field_names
    assert "compose_max_depth" in field_names
    assert "compose_json_chat_fn" in field_names
    assert "llm_settings" in field_names


def test_e2e_result_has_compose_fields() -> None:
    from tsumiki.runner.e2e import E2EResult

    field_names = {f.name for f in fields(E2EResult)}
    assert "compose_selected_modules" in field_names
    assert "compose_search_score" in field_names


def test_e2e_config_use_compose_defaults_false() -> None:
    """use_compose のデフォルトは False (Phase 5c 互換動作)."""
    from tsumiki.runner.e2e import E2EConfig

    use_compose_field = next(
        f for f in fields(E2EConfig) if f.name == "use_compose"
    )
    assert use_compose_field.default is False


# === _run_compose_auxiliary smoke (mock DI) ===


def test_run_compose_auxiliary_smoke() -> None:
    """`_run_compose_auxiliary` が mock DI で動作し selected_modules を返す."""
    from tsumiki.runner.e2e import E2EConfig, _run_compose_auxiliary

    def mock_chat(prompt: str):
        # ChatResult 型を持つラッパ. _to_text_chat_fn は .content を取る.
        class _Res:
            content = (
                "{'planning': 'IO', 'reasoning': 'IO', "
                "'tooluse': 'None', 'memory': 'None'}"
            )

        return _Res()

    def mock_json_chat(_msg_list):
        return {
            "name": "MockModule",
            "thought": "mock",
            "module type": "reasoning",
            "code": "pass",
        }

    cfg = E2EConfig(
        goal="test",
        clean_clauses=(),
        seed=42,
        n_synth_per_pattern=1,
        runtime_model="test-model",
        evaluator_root=__import__("pathlib").Path("/tmp"),
        parser_chat_fn=mock_chat,
        generator_chat_fn=mock_chat,
        runtime_chat_fn=mock_chat,
        mlflow_experiment="test",
        outcomes_dir=None,
        auto_approve_eval=True,
        generated_at="2026-06-19",
        approved_by="auto",
        modifier_reuse_prompt_version="v0",
        modifier_zerobase_prompt_version="v0",
        detector_prompt_version="v0",
        use_compose=True,
        compose_max_depth=1,
        compose_json_chat_fn=mock_json_chat,
        llm_settings=_settings(),
    )

    selected, score = _run_compose_auxiliary(
        cfg=cfg,
        ts=_task_spec(),
        spec=_eval_spec(),
        ng_book=_knowledge(),
        reuse_sr=0.42,
    )
    assert set(selected.keys()) == {"planning", "reasoning", "tooluse", "memory"}
    # benchmark_fn は trivial で常に reuse_sr を返すため最終 score は 0.42
    assert score == 0.42


def test_run_compose_auxiliary_raises_when_llm_settings_missing() -> None:
    """use_compose=True なのに llm_settings が None なら明示 raise."""
    import pytest

    from tsumiki.runner.e2e import E2EConfig, _run_compose_auxiliary

    cfg = E2EConfig(
        goal="test",
        clean_clauses=(),
        seed=42,
        n_synth_per_pattern=1,
        runtime_model="test-model",
        evaluator_root=__import__("pathlib").Path("/tmp"),
        parser_chat_fn=lambda _p: None,  # type: ignore[arg-type]
        generator_chat_fn=lambda _p: None,  # type: ignore[arg-type]
        runtime_chat_fn=lambda _p: None,  # type: ignore[arg-type]
        mlflow_experiment="test",
        outcomes_dir=None,
        auto_approve_eval=True,
        generated_at="2026-06-19",
        approved_by="auto",
        modifier_reuse_prompt_version="v0",
        modifier_zerobase_prompt_version="v0",
        detector_prompt_version="v0",
        use_compose=True,
        compose_max_depth=1,
        compose_json_chat_fn=lambda _m: {},
        llm_settings=None,
    )
    with pytest.raises(ValueError, match="llm_settings"):
        _run_compose_auxiliary(
            cfg=cfg,
            ts=_task_spec(),
            spec=_eval_spec(),
            ng_book=_knowledge(),
            reuse_sr=0.0,
        )


def test_run_compose_auxiliary_raises_when_json_chat_fn_missing() -> None:
    """use_compose=True なのに compose_json_chat_fn が None なら明示 raise."""
    import pytest

    from tsumiki.runner.e2e import E2EConfig, _run_compose_auxiliary

    cfg = E2EConfig(
        goal="test",
        clean_clauses=(),
        seed=42,
        n_synth_per_pattern=1,
        runtime_model="test-model",
        evaluator_root=__import__("pathlib").Path("/tmp"),
        parser_chat_fn=lambda _p: None,  # type: ignore[arg-type]
        generator_chat_fn=lambda _p: None,  # type: ignore[arg-type]
        runtime_chat_fn=lambda _p: None,  # type: ignore[arg-type]
        mlflow_experiment="test",
        outcomes_dir=None,
        auto_approve_eval=True,
        generated_at="2026-06-19",
        approved_by="auto",
        modifier_reuse_prompt_version="v0",
        modifier_zerobase_prompt_version="v0",
        detector_prompt_version="v0",
        use_compose=True,
        compose_max_depth=1,
        compose_json_chat_fn=None,
        llm_settings=_settings(),
    )
    with pytest.raises(ValueError, match="compose_json_chat_fn"):
        _run_compose_auxiliary(
            cfg=cfg,
            ts=_task_spec(),
            spec=_eval_spec(),
            ng_book=_knowledge(),
            reuse_sr=0.0,
        )
