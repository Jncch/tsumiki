"""TaskSpec / EvaluatorSpec の dataclass 定義.

Phase 5c で導入。自然言語の目的をフレーム内で扱える構造化表現にする。

設計: docs/experiments/phase5c_design.md §1.3, §1.4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# 主要タスククラス. Phase 5c で 5 種、Phase 9a で 5 種追加。
# 「動詞」を表すラベルとし、形態 (閉じた/開放) は output_kind で持つ (設計 phase9_design §3.1).
TaskClass = Literal[
    # Phase 5c 既存
    "detect",
    "modify",
    "detect_and_modify",
    "extract",
    "compare",
    # Phase 9a 追加
    "generate",
    "compose",
    "summarize",
    "transform",
    "infer",
]
# 評価器の中身. Q3=B により決定関数 + LLM judge + ハイブリッドを許容.
# Phase 9c で llm_judge_panel / llm_judge_pairwise を追加予定 (本フェーズでは追加しない).
EvaluatorType = Literal["deterministic", "llm_judge", "hybrid"]
# 入力の役割. target=チェック対象, reference=参照資料, rule=社内ルール, intent=自然言語の意図文.
# Phase 9a で intent / record / focus を追加 (開放タスク / 非ドキュメント入力用).
InputRoleKind = Literal["target", "reference", "rule", "intent", "record", "focus"]
# 知識源の種別.
KnowledgeSourceType = Literal["existing", "extract", "hybrid"]

# Phase 9a: タスク形態の直交軸. closed=決定論的に正解、semi_open=部分的、open=自由度高い.
OutputKind = Literal["closed", "semi_open", "open"]

# Phase 9a: 入力モダリティの直交軸. doc=ドキュメント、free_text=自然言語、
# structured=構造化データ、mixed=混在、none=入力なし.
InputModality = Literal["doc", "free_text", "structured", "mixed", "none"]


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
    Phase 9a で output_kind / input_modality を追加. デフォルト値は既存挙動互換.
    """

    task_class: TaskClass
    domain: str
    input_roles: tuple[InputRole, ...]
    knowledge: KnowledgeSource
    outputs: tuple[OutputSchema, ...]
    evaluator_hints: tuple[str, ...] = field(default_factory=tuple)
    raw_goal: str = ""  # 自然言語の原文 (監査用)
    # Phase 9a 追加. デフォルトは既存 NDA/ISO27001 互換 (closed + doc).
    output_kind: OutputKind = "closed"
    input_modality: InputModality = "doc"

    def io_signature(self) -> tuple[tuple[str, str], tuple[tuple[str, str], ...]]:
        """流用蓄積検索用の入出力シグネチャ.

        入力役割の name + role の組と、出力の name + schema_id の組を返す.
        """
        input_sig = tuple(sorted((r.name, r.role) for r in self.input_roles))
        output_sig = tuple(sorted((o.name, o.schema_id) for o in self.outputs))
        return input_sig, output_sig

    def is_open_ended(self) -> bool:
        """開放タスクかを返す.

        Phase 9a (2026-06-20) で追加. output_kind が "semi_open" / "open" のとき True.
        dispatcher が対話パスへ分岐する判定に使う (Phase 9b の dialog REPL).
        """
        return self.output_kind in ("semi_open", "open")

    def has_document_input(self) -> bool:
        """ドキュメント入力を含むかを返す.

        Phase 9a (2026-06-20) で追加. input_modality が "doc" / "mixed" のとき True.
        sample 合成戦略の切替に使う (Phase 9e の統一 runner).
        """
        return self.input_modality in ("doc", "mixed")

    def has_input(self) -> bool:
        """そもそも入力データを持つかを返す.

        Phase 9a (2026-06-20) で追加. input_modality が "none" でないとき True.
        "none" の場合は raw_goal だけから生成する (例: キャンペーン案).
        """
        return self.input_modality != "none"


@dataclass(frozen=True)
class TestCase:
    """評価器の単体テスト 1 ケース."""

    # pytest が "TestCase" を test class として収集しようとする誤検出を抑える.
    __test__ = False

    name: str
    input: dict
    expected: dict


@dataclass(frozen=True)
class EvaluatorSpec:
    """評価器の構造化表現. goal/generator.py が LLM 生成し、ユーザーが承認する.

    type=llm_judge / hybrid のときは guardrails に少なくとも 1 つのガードレールを要する.
    Phase 9a で output_kind を追加. デフォルト値は既存挙動互換.
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
    # Phase 9a 追加. デフォルトは既存 NDA/ISO27001 互換 (closed).
    # 開放タスク評価器との誤マッチを防ぐため lookup 時にも比較する (Phase 9b).
    output_kind: OutputKind = "closed"

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
