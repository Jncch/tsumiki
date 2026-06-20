"""評価軸テンプレ schema + loader.

Phase 9b 設計 §3.3 に対応. _common/ にドメイン非依存の汎用軸を持ち,
<domain>/ にドメイン固有軸を merge する階層構造.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

EvalDimensionType = Literal[
    "deterministic",
    "llm_judge",
    "llm_judge_panel",
    "llm_judge_pairwise",
    "hybrid",
]


@dataclass(frozen=True)
class EvalDimensionParameter:
    """評価軸のパラメータ仕様 (テンプレ穴埋め用)."""

    name: str
    type: str
    required: bool = False
    default: Any = None
    description: str = ""


@dataclass(frozen=True)
class EvalDimension:
    """評価軸 1 つの仕様. YAML から load される.

    deterministic 系は implementation_template を, llm_judge_* 系は
    prompt_template を持つ. hybrid は両方持ち得る.
    """

    id: str
    label: str
    type: EvalDimensionType
    applicable_task_classes: tuple[str, ...]
    applicable_output_kinds: tuple[str, ...]
    description: str = ""
    parameters: tuple[EvalDimensionParameter, ...] = field(default_factory=tuple)
    implementation_template: str | None = None
    prompt_template: str | None = None
    guardrails: tuple[str, ...] = field(default_factory=tuple)
    typical_success_example: dict | None = None
    typical_failure_example: dict | None = None
    source_domain: str = "_common"

    def matches(self, task_class: str, output_kind: str) -> bool:
        """この評価軸が指定タスクに適用可能かを返す."""
        return (
            task_class in self.applicable_task_classes
            and output_kind in self.applicable_output_kinds
        )


def _load_dimension_yaml(path: Path, source_domain: str) -> EvalDimension:
    """1 つの YAML ファイルから EvalDimension を作る."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    parameters = tuple(
        EvalDimensionParameter(
            name=p["name"],
            type=p["type"],
            required=p.get("required", False),
            default=p.get("default"),
            description=p.get("description", ""),
        )
        for p in data.get("parameters", []) or []
    )
    return EvalDimension(
        id=data["id"],
        label=data["label"],
        type=data["type"],
        applicable_task_classes=tuple(data.get("applicable_task_classes", []) or []),
        applicable_output_kinds=tuple(data.get("applicable_output_kinds", []) or []),
        description=data.get("description", ""),
        parameters=parameters,
        implementation_template=data.get("implementation_template"),
        prompt_template=data.get("prompt_template"),
        guardrails=tuple(data.get("guardrails", []) or []),
        typical_success_example=data.get("typical_success_example"),
        typical_failure_example=data.get("typical_failure_example"),
        source_domain=source_domain,
    )


def load_eval_dimensions(
    root: Path,
    domain: str | None = None,
) -> tuple[EvalDimension, ...]:
    """評価軸テンプレを root/_common/ と root/<domain>/ からロードする.

    ID 重複時はドメイン固有テンプレが _common/ を上書きする (override).
    domain が None または root/<domain>/ が存在しない場合は _common/ のみ.
    """
    common_dir = root / "_common"
    if not common_dir.is_dir():
        raise FileNotFoundError(f"_common directory not found under {root}")

    by_id: dict[str, EvalDimension] = {}
    for yml in sorted(common_dir.glob("*.yaml")):
        d = _load_dimension_yaml(yml, source_domain="_common")
        by_id[d.id] = d

    if domain:
        domain_dir = root / domain
        if domain_dir.is_dir():
            for yml in sorted(domain_dir.glob("*.yaml")):
                d = _load_dimension_yaml(yml, source_domain=domain)
                by_id[d.id] = d  # override _common

    return tuple(by_id.values())


def filter_applicable(
    dimensions: tuple[EvalDimension, ...],
    task_class: str,
    output_kind: str,
) -> tuple[EvalDimension, ...]:
    """task_class + output_kind に適用可能な軸だけ抽出する."""
    return tuple(d for d in dimensions if d.matches(task_class, output_kind))


__all__ = [
    "EvalDimension",
    "EvalDimensionParameter",
    "EvalDimensionType",
    "filter_applicable",
    "load_eval_dimensions",
]
