"""MLflow ロガーのテスト. tmp_path で file:// バックエンドを使う."""

from __future__ import annotations

from pathlib import Path

import mlflow
import pytest

from tsumiki.eval import ClauseLabel, ClausePrediction, compute_metrics
from tsumiki.exp import log_metrics_report, log_run_params, setup_tracking


def _make_report() -> object:
    truth = [
        ClauseLabel(clause_id="c1", contract_type="nda", text="", ng_pattern_ids=frozenset({"A"})),
        ClauseLabel(clause_id="c2", contract_type="nda", text="", ng_pattern_ids=frozenset({"B"})),
        ClauseLabel(clause_id="c3", contract_type="nda", text="", ng_pattern_ids=frozenset()),
    ]
    pred = [
        ClausePrediction(clause_id="c1", ng_pattern_ids=frozenset({"A"})),
        ClausePrediction(clause_id="c2", ng_pattern_ids=frozenset()),
        ClausePrediction(clause_id="c3", ng_pattern_ids=frozenset()),
    ]
    return compute_metrics(truth, pred, ["A", "B"])


_BASE_PARAMS = {
    "model": "qwen2.5:14b-instruct-q4_K_M",
    "quantization_tag": "q4_K_M",
    "prompt_version": "v0.1.0",
    "seed": 42,
    "temperature": 0.0,
    "contract_type": "nda",
    "phase": "phase1_baseline",
}


def _setup(tmp_path: Path) -> str:
    return setup_tracking(f"file:{tmp_path / 'mlruns'}")


def test_log_run_records_required_params_and_metrics(tmp_path: Path) -> None:
    uri = _setup(tmp_path)
    mlflow.set_experiment("test_required_params")
    with mlflow.start_run(run_name="r1") as run:
        log_run_params(_BASE_PARAMS)
        report = _make_report()
        log_metrics_report(report)  # type: ignore[arg-type]

    client = mlflow.MlflowClient(tracking_uri=uri)
    fetched = client.get_run(run.info.run_id)
    for key in _BASE_PARAMS:
        assert key in fetched.data.params
    assert "ollama_version" in fetched.data.params
    assert "macro_recall" in fetched.data.metrics


def test_missing_required_param_raises(tmp_path: Path) -> None:
    _setup(tmp_path)
    mlflow.set_experiment("test_missing")
    partial = {k: v for k, v in _BASE_PARAMS.items() if k != "seed"}
    with mlflow.start_run(run_name="r_missing"):
        with pytest.raises(ValueError, match="seed"):
            log_run_params(partial)


def test_per_pattern_metrics_present(tmp_path: Path) -> None:
    uri = _setup(tmp_path)
    mlflow.set_experiment("test_per_pattern")
    with mlflow.start_run(run_name="r_pp") as run:
        log_run_params(_BASE_PARAMS)
        log_metrics_report(_make_report())  # type: ignore[arg-type]

    client = mlflow.MlflowClient(tracking_uri=uri)
    metrics = client.get_run(run.info.run_id).data.metrics
    assert "recall.A" in metrics
    assert "recall.B" in metrics
    assert "support.A" in metrics
