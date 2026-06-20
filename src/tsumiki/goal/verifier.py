"""生成された EvaluatorSpec の test_cases を実行して検証する.

Q2=C ユーザー承認フローの一部. LLM 生成の評価器が test_cases.expected と
一致するかを確認し、ユーザー承認の判断材料を提供する.

設計: docs/experiments/phase5c_design.md §1.4, §3.2
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tsumiki.goal.specs import EvaluatorSpec


EvaluateFn = Callable[[list[dict]], dict]


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    failures: tuple[str, ...]
    error: str | None


def load_evaluate_callable(
    implementation: str, *, module_suffix: str = "loaded"
) -> EvaluateFn:
    """implementation 文字列を一時ファイル経由でロードし evaluate 関数を返す."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    )
    try:
        tmp.write(implementation)
        tmp.flush()
        tmp.close()
        path = Path(tmp.name)
        module_name = f"tsumiki_eval_{path.stem}_{module_suffix}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot create module spec from {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        fn = getattr(module, "evaluate", None)
        if fn is None or not callable(fn):
            raise AttributeError(
                "implementation must define `evaluate(outcomes) -> dict`"
            )
        return fn
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def load_evaluator_from_path(path: Path) -> EvaluateFn:
    """eval/generated/<...>/evaluator.py から evaluate 関数をロードする."""
    text = path.read_text(encoding="utf-8")
    return load_evaluate_callable(text, module_suffix=path.parent.name)


def verify(spec: EvaluatorSpec, *, tolerance: float = 1e-9) -> VerificationResult:
    """test_cases.expected と evaluate(outcomes) の出力を比較する.

    数値は tolerance 以内の差を許容する. それ以外は厳密一致.
    """
    try:
        evaluate = load_evaluate_callable(spec.implementation)
    except Exception as e:  # noqa: BLE001
        return VerificationResult(passed=False, failures=(), error=str(e))
    failures: list[str] = []
    for tc in spec.test_cases:
        outcomes = tc.input.get("outcomes", []) if isinstance(tc.input, dict) else []
        try:
            got = evaluate(list(outcomes))
        except Exception as e:  # noqa: BLE001
            failures.append(f"{tc.name}: raised {type(e).__name__}: {e!s}")
            continue
        for key, expected in tc.expected.items():
            actual = got.get(key)
            if _values_equal(actual, expected, tolerance=tolerance):
                continue
            failures.append(
                f"{tc.name}: {key} mismatch: expected={expected!r}, got={actual!r}"
            )
    return VerificationResult(
        passed=not failures, failures=tuple(failures), error=None
    )


def _values_equal(actual: object, expected: object, *, tolerance: float) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(float(actual) - float(expected)) <= tolerance
    return actual == expected
