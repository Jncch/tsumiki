"""TaskSpec / EvaluatorSpec の dataclass 定義.

Phase 5c で導入。自然言語の目的をフレーム内で扱える構造化表現にする。

設計: docs/experiments/phase5c_design.md §1.3, §1.4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# 主要タスククラス。Phase 5c では 5 種。将来追加可能。
TaskClass = Literal["detect", "modify", "detect_and_modify", "extract", "compare"]
# 評価器の中身. Q3=B により決定関数 + LLM judge + ハイブリッドを許容.
EvaluatorType = Literal["deterministic", "llm_judge", "hybrid"]
# 入力の役割. target=チェック対象, reference=参照資料, rule=社内ルール.
InputRoleKind = Literal["target", "reference", "rule"]
# 知識源の種別.
KnowledgeSourceType = Literal["existing", "extract", "hybrid"]


@dataclass(frozen=True)
class InputRole:
    """目的が要求する入力 1 つの仕様."""

    name: str  # target_document, reference_set, etc.
    formats: tuple[str, ...]  # pdf, docx, md, txt, jsonl など
    role: InputRoleKind
    description: str = ""


@dataclass(frozen=True)
class KnowledgeSource:
    """目的に必要な知識をどう調達するか.

    source_type="existing" のときは catalog_path を必須にする (Knowledge 層を再利用).
    "extract" は入力から LLM 抽出. "hybrid" は両方併用.
    """

    source_type: KnowledgeSourceType
    catalog_path: str | None = None
    extraction_hints: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OutputSchema:
    """目的の出力 1 つの仕様."""

    name: str  # findings, modified_document, etc.
    schema_id: str  # ng_findings_v1 など. EvaluatorSpec lookup の検索キー
    description: str = ""


@dataclass(frozen=True)
class TaskSpec:
    """目的の構造化表現. goal/parser.py が自然言語から生成する.

    流用蓄積の検索キー (Q4=B) は domain + task_class + 入出力スキーマの一致.
    """

    task_class: TaskClass
    domain: str
    input_roles: tuple[InputRole, ...]
    knowledge: KnowledgeSource
    outputs: tuple[OutputSchema, ...]
    evaluator_hints: tuple[str, ...] = field(default_factory=tuple)
    raw_goal: str = ""  # 自然言語の原文 (監査用)

    def io_signature(self) -> tuple[tuple[str, str], tuple[tuple[str, str], ...]]:
        """流用蓄積検索用の入出力シグネチャ.

        入力役割の name + role の組と、出力の name + schema_id の組を返す.
        """
        input_sig = tuple(sorted((r.name, r.role) for r in self.input_roles))
        output_sig = tuple(sorted((o.name, o.schema_id) for o in self.outputs))
        return input_sig, output_sig


@dataclass(frozen=True)
class TestCase:
    """評価器の単体テスト 1 ケース."""

    name: str
    input: dict
    expected: dict


@dataclass(frozen=True)
class EvaluatorSpec:
    """評価器の構造化表現. goal/generator.py が LLM 生成し、ユーザーが承認する.

    type=llm_judge / hybrid のときは guardrails に少なくとも 1 つのガードレールを要する.
    """

    id: str
    domain: str
    task_class: TaskClass
    type: EvaluatorType
    input_signature: tuple[tuple[str, str], tuple[tuple[str, str], ...]]
    output_metrics: tuple[str, ...]
    implementation: str  # Python ソースコード or LLM judge プロンプトテンプレート
    test_cases: tuple[TestCase, ...]
    guardrails: tuple[str, ...]  # pairwise, panel_3, human_calibration
    sources: tuple[str, ...]  # 参照した既存実装 / 文献
    generated_at: str  # ISO 日付
    approved_by: str
    notes: str = ""  # 既知の偏り、適用条件など

    def __post_init__(self) -> None:
        if self.type in ("llm_judge", "hybrid") and not self.guardrails:
            raise ValueError(
                f"evaluator {self.id!r} of type {self.type!r} must have at least one guardrail"
            )

    def is_approved(self) -> bool:
        """評価器が承認済かを返す.

        Phase 7e-5 (2026-06-19) で追加. CLAUDE.md §9 (評価器が無い状態で自動探索を回さない)
        の判定子. lookup hit (`approved_by="auto"`) または generator + verify 通過
        (`approved_by="<user>"`) で承認済とみなす.

        `tsumiki.policy.compose._assert_evaluator_gate_passed` が本メソッドを使う.
        """
        return bool(self.approved_by)
