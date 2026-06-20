"""EvaluatorSpec の保存・読み込み.

承認済み評価器を `<root>/eval/generated/<domain>/<task_class>/<evaluator_id>/` に保存し、
後続フェーズ・別ドメインから流用できる形にする.

設計: docs/experiments/phase5c_design.md §2 `goal/store.py`
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from tsumiki.goal.specs import EvaluatorSpec, TestCase

EVALUATOR_PY = "evaluator.py"
META_YAML = "meta.yaml"
TEST_CASES_JSONL = "test_cases.jsonl"
README_MD = "README.md"


def evaluator_dir(root: Path, spec: EvaluatorSpec) -> Path:
    """評価器の保存先ディレクトリパスを組み立てる."""
    return root / spec.domain / spec.task_class / spec.id


def save(root: Path, spec: EvaluatorSpec) -> Path:
    """EvaluatorSpec を 4 ファイルに分けて保存する.

    Returns: 保存ディレクトリのパス.
    """
    out_dir = evaluator_dir(root, spec)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / EVALUATOR_PY).write_text(spec.implementation, encoding="utf-8")

    meta = {
        "id": spec.id,
        "domain": spec.domain,
        "task_class": spec.task_class,
        "type": spec.type,
        "input_signature": {
            "inputs": [list(t) for t in spec.input_signature[0]],
            "outputs": [list(t) for t in spec.input_signature[1]],
        },
        "output_metrics": list(spec.output_metrics),
        "guardrails": list(spec.guardrails),
        "sources": list(spec.sources),
        "generated_at": spec.generated_at,
        "approved_by": spec.approved_by,
        "notes": spec.notes,
    }
    (out_dir / META_YAML).write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    with (out_dir / TEST_CASES_JSONL).open("w", encoding="utf-8") as f:
        for tc in spec.test_cases:
            rec = {"name": tc.name, "input": tc.input, "expected": tc.expected}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    readme = _render_readme(spec)
    (out_dir / README_MD).write_text(readme, encoding="utf-8")

    return out_dir


def load(eval_dir: Path) -> EvaluatorSpec:
    """保存済み評価器ディレクトリから EvaluatorSpec を復元する."""
    meta_path = eval_dir / META_YAML
    impl_path = eval_dir / EVALUATOR_PY
    tc_path = eval_dir / TEST_CASES_JSONL
    if not meta_path.is_file():
        raise FileNotFoundError(f"meta.yaml not found: {meta_path}")
    if not impl_path.is_file():
        raise FileNotFoundError(f"evaluator.py not found: {impl_path}")

    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    if not isinstance(meta, dict):
        raise ValueError(f"meta.yaml root must be a mapping: {meta_path}")
    implementation = impl_path.read_text(encoding="utf-8")

    test_cases: list[TestCase] = []
    if tc_path.is_file():
        with tc_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                test_cases.append(
                    TestCase(
                        name=str(rec.get("name", "")),
                        input=dict(rec.get("input", {})),
                        expected=dict(rec.get("expected", {})),
                    )
                )

    sig = meta.get("input_signature", {})
    inputs = tuple(tuple(t) for t in sig.get("inputs", []) or [])
    outputs = tuple(tuple(t) for t in sig.get("outputs", []) or [])

    return EvaluatorSpec(
        id=str(meta["id"]),
        domain=str(meta["domain"]),
        task_class=meta["task_class"],
        type=meta["type"],
        input_signature=(inputs, outputs),
        output_metrics=tuple(meta.get("output_metrics", []) or []),
        implementation=implementation,
        test_cases=tuple(test_cases),
        guardrails=tuple(meta.get("guardrails", []) or []),
        sources=tuple(meta.get("sources", []) or []),
        generated_at=str(meta.get("generated_at", "")),
        approved_by=str(meta.get("approved_by", "")),
        notes=str(meta.get("notes", "")),
    )


def _render_readme(spec: EvaluatorSpec) -> str:
    lines: list[str] = []
    lines.append(f"# Evaluator: {spec.id}")
    lines.append("")
    lines.append(f"- domain: `{spec.domain}`")
    lines.append(f"- task_class: `{spec.task_class}`")
    lines.append(f"- type: `{spec.type}`")
    lines.append(f"- generated_at: {spec.generated_at}")
    lines.append(f"- approved_by: {spec.approved_by}")
    lines.append("")
    lines.append("## 出力指標")
    lines.append("")
    for m in spec.output_metrics:
        lines.append(f"- {m}")
    if spec.guardrails:
        lines.append("")
        lines.append("## ガードレール")
        lines.append("")
        for g in spec.guardrails:
            lines.append(f"- {g}")
    if spec.sources:
        lines.append("")
        lines.append("## 参照元")
        lines.append("")
        for s in spec.sources:
            lines.append(f"- {s}")
    if spec.notes:
        lines.append("")
        lines.append("## 既知の偏り / 適用条件")
        lines.append("")
        lines.append(spec.notes)
    lines.append("")
    return "\n".join(lines)
