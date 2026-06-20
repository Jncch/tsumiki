"""対話質問テンプレ schema + loader.

Phase 9b で Python 定数として実装した Q1〜Q10 を Phase 9b+ (2026-06-20 改訂) で
YAML 外部化. 評価軸テンプレ (eval_dimensions) と同じ階層構造:

- `_common/<stage>.yaml`  : ドメイン非依存の汎用質問
- `<domain>/<stage>.yaml` : ドメイン固有の質問 (_common を override)

Literal 整合性は loader でランタイム検証. allowed_values は
`tsumiki.goal.specs` の Literal 型の subset であることを起動時に確認する.
これにより YAML 外部化しても型安全性を維持.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, get_args

import yaml

from tsumiki.goal.specs import (
    InputModality,
    InputRoleKind,
    OutputKind,
    TaskClass,
)

ExpectedType = Literal["str", "literal", "list", "yes_no"]
StageName = Literal["task_spec", "dimensions", "approve"]


# YAML 上の `validate_against_literal` フィールドで指定された名前を
# 対応する Literal 型に解決するための辞書.
LITERAL_REGISTRY: dict[str, tuple[str, ...]] = {
    "TaskClass": get_args(TaskClass),
    "OutputKind": get_args(OutputKind),
    "InputModality": get_args(InputModality),
    "InputRoleKind": get_args(InputRoleKind),
}


@dataclass(frozen=True)
class DialogQuestion:
    """1 つの構造化質問の仕様 (YAML 由来)."""

    id: str
    prompt: str
    expected_type: ExpectedType
    allowed_values: tuple[str, ...] = ()
    description: str = ""
    llm_suggest: bool = False
    validate_against_literal: str = ""  # "TaskClass" / "OutputKind" / ... or ""

    def __post_init__(self) -> None:
        # Literal 整合性チェック.
        if self.validate_against_literal:
            registered = LITERAL_REGISTRY.get(self.validate_against_literal)
            if registered is None:
                raise ValueError(
                    f"question {self.id!r}: 未知の Literal 名 "
                    f"{self.validate_against_literal!r}. LITERAL_REGISTRY を更新してください"
                )
            illegal = set(self.allowed_values) - set(registered)
            if illegal:
                raise ValueError(
                    f"question {self.id!r}: allowed_values に "
                    f"{self.validate_against_literal} に無い値が含まれます: {illegal}"
                )


@dataclass(frozen=True)
class StageQuestions:
    """1 つの stage に属する質問群 (YAML 1 ファイル分)."""

    stage: StageName
    title: str
    questions: tuple[DialogQuestion, ...]
    source_domain: str = "_common"


def _load_question_dict(data: dict[str, Any]) -> DialogQuestion:
    """YAML 1 質問分の dict を DialogQuestion に変換."""
    return DialogQuestion(
        id=data["id"],
        prompt=data["prompt"],
        expected_type=data["expected_type"],
        allowed_values=tuple(data.get("allowed_values", []) or []),
        description=data.get("description", ""),
        llm_suggest=bool(data.get("llm_suggest", False)),
        validate_against_literal=data.get("validate_against_literal", ""),
    )


def _load_stage_yaml(path: Path, source_domain: str) -> StageQuestions:
    """1 つの stage YAML から StageQuestions を作る."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    questions = tuple(_load_question_dict(q) for q in data.get("questions", []) or [])
    return StageQuestions(
        stage=data["stage"],
        title=data.get("title", ""),
        questions=questions,
        source_domain=source_domain,
    )


def load_dialog_questions(
    root: Path,
    stage: StageName,
    domain: str | None = None,
) -> StageQuestions:
    """指定 stage の質問テンプレを root/_common/<stage>*.yaml と
    root/<domain>/<stage>*.yaml から階層的にロードする.

    ドメイン固有テンプレが存在すれば _common を上書きする.
    """
    common_dir = root / "_common"
    if not common_dir.is_dir():
        raise FileNotFoundError(f"_common directory not found under {root}")

    common_files = sorted(common_dir.glob(f"*{stage}*.yaml"))
    if not common_files:
        raise FileNotFoundError(
            f"stage={stage!r} に対応する YAML が {common_dir} に見つかりません"
        )
    # 同 stage 内で複数 YAML がある場合は最初の 1 つを採用 (現状の運用は 1 ファイル/stage)
    common = _load_stage_yaml(common_files[0], source_domain="_common")

    if domain:
        domain_files = sorted((root / domain).glob(f"*{stage}*.yaml"))
        if domain_files:
            return _load_stage_yaml(domain_files[0], source_domain=domain)

    return common


@dataclass(frozen=True)
class DialogQuestionsBundle:
    """3 stage 分の質問をまとめたコンテナ (Phase 9b 改訂)."""

    task_spec: StageQuestions
    dimensions: StageQuestions
    approve: StageQuestions
    source_root: Path = field(default_factory=lambda: Path("."))

    def all_questions(self) -> tuple[DialogQuestion, ...]:
        return self.task_spec.questions + self.dimensions.questions + self.approve.questions


def load_all_dialog_questions(
    root: Path,
    domain: str | None = None,
) -> DialogQuestionsBundle:
    """全 stage の質問を 1 度にロード."""
    return DialogQuestionsBundle(
        task_spec=load_dialog_questions(root, "task_spec", domain),
        dimensions=load_dialog_questions(root, "dimensions", domain),
        approve=load_dialog_questions(root, "approve", domain),
        source_root=root,
    )


__all__ = [
    "DialogQuestion",
    "DialogQuestionsBundle",
    "ExpectedType",
    "LITERAL_REGISTRY",
    "StageName",
    "StageQuestions",
    "load_all_dialog_questions",
    "load_dialog_questions",
]
