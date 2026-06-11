"""MLflow ロガー: 必須記録項目を漏れなく残すための薄いラッパ.

設計方針:
- 既存の mlflow API をラップしすぎず、明示的に併用できる形で薄く書く。
- CLAUDE.md §4 の必須項目は `log_run_params` で標準セット化する。
- 評価指標は MetricsReport → log_metric の橋渡しのみ。
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any

import mlflow

from tsumiki.eval.metrics import MetricsReport

_REQUIRED_PARAM_KEYS = frozenset(
    {
        "model",
        "quantization_tag",
        "prompt_version",
        "seed",
        "temperature",
        "contract_type",
        "phase",
    }
)
# MLflow のパラメタ名は英数・アンダースコア等に制限されるので簡易サニタイズ
_PARAM_NAME_BAD = re.compile(r"[^A-Za-z0-9_./-]")


def setup_tracking(tracking_uri: str | None = None) -> str:
    """MLflow の tracking URI を設定して返す."""
    uri = tracking_uri or os.environ.get("MLFLOW_TRACKING_URI", "file:./mlruns")
    mlflow.set_tracking_uri(uri)
    return uri


def get_ollama_version() -> str:
    """ホスト ollama のバージョンを取得. 失敗時は 'unknown'."""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"
    text = (result.stdout or result.stderr or "").strip()
    # 出力例: "ollama version is 0.30.6" や "client version is 0.30.6"
    m = re.search(r"(\d+\.\d+\.\d+)", text)
    return m.group(1) if m else (text.splitlines()[0] if text else "unknown")


def log_run_params(params: dict[str, Any], *, require_full_set: bool = True) -> None:
    """run-level の設定をログする.

    `require_full_set` が True (既定) のとき、CLAUDE.md §4 の必須項目が
    すべて含まれているか検証する。不足はエラーにする（後出しを防ぐ）。
    実行時に ollama_version を自動付与する。
    """
    missing = _REQUIRED_PARAM_KEYS - params.keys()
    if require_full_set and missing:
        raise ValueError(f"missing required params: {sorted(missing)}")
    enriched = {"ollama_version": get_ollama_version(), **params}
    for k, v in enriched.items():
        safe_key = _PARAM_NAME_BAD.sub("_", k)
        mlflow.log_param(safe_key, v)


def log_metrics_report(report: MetricsReport, prefix: str = "") -> None:
    """MetricsReport を MLflow の log_metric に展開する."""
    p = f"{prefix}." if prefix else ""
    mlflow.log_metric(f"{p}macro_recall", report.macro_recall)
    mlflow.log_metric(f"{p}macro_precision", report.macro_precision)
    mlflow.log_metric(f"{p}macro_fbeta", report.macro_fbeta)
    mlflow.log_metric(f"{p}weighted_recall", report.weighted_recall)
    mlflow.log_metric(f"{p}weighted_precision", report.weighted_precision)
    mlflow.log_metric(f"{p}weighted_fbeta", report.weighted_fbeta)
    mlflow.log_metric(f"{p}total_support", float(report.total_support))
    mlflow.log_metric(f"{p}beta", report.beta)
    for per in report.per_pattern:
        pid = _PARAM_NAME_BAD.sub("_", per.pattern_id)
        mlflow.log_metric(f"{p}recall.{pid}", per.recall)
        mlflow.log_metric(f"{p}precision.{pid}", per.precision)
        mlflow.log_metric(f"{p}fbeta.{pid}", per.fbeta)
        mlflow.log_metric(f"{p}support.{pid}", float(per.support))
