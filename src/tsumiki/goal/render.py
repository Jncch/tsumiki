"""TaskSpec / EvaluatorSpec を YAML として表示するユーティリティ.

ユーザー承認フロー (Q1=C, Q2=C) で「フレームが LLM 経由でこう解釈しました」
を提示するために使う.
"""

from __future__ import annotations

import yaml

from tsumiki.goal.specs import EvaluatorSpec, TaskSpec


def task_spec_to_dict(spec: TaskSpec) -> dict:
    return {
        "task_class": spec.task_class,
        "domain": spec.domain,
        "input_roles": [
            {
                "name": r.name,
                "formats": list(r.formats),
                "role": r.role,
                "description": r.description,
            }
            for r in spec.input_roles
        ],
        "knowledge": {
            "source_type": spec.knowledge.source_type,
            "catalog_path": spec.knowledge.catalog_path,
            "extraction_hints": list(spec.knowledge.extraction_hints),
        },
        "outputs": [
            {
                "name": o.name,
                "schema_id": o.schema_id,
                "description": o.description,
            }
            for o in spec.outputs
        ],
        "evaluator_hints": list(spec.evaluator_hints),
    }


def task_spec_to_yaml(spec: TaskSpec) -> str:
    return yaml.safe_dump(
        task_spec_to_dict(spec),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def evaluator_spec_summary(spec: EvaluatorSpec) -> str:
    """承認フロー用に EvaluatorSpec の要点を Markdown で返す."""
    lines: list[str] = []
    lines.append(f"# Evaluator {spec.id}")
    lines.append("")
    lines.append(f"- domain: `{spec.domain}`")
    lines.append(f"- task_class: `{spec.task_class}`")
    lines.append(f"- type: `{spec.type}`")
    lines.append(f"- output_metrics: {', '.join(spec.output_metrics)}")
    if spec.guardrails:
        lines.append(f"- guardrails: {', '.join(spec.guardrails)}")
    lines.append("")
    lines.append("## implementation")
    lines.append("")
    lines.append("```python")
    lines.append(spec.implementation.rstrip())
    lines.append("```")
    if spec.test_cases:
        lines.append("")
        lines.append("## test_cases")
        lines.append("")
        for tc in spec.test_cases:
            lines.append(f"- {tc.name}")
    return "\n".join(lines)
