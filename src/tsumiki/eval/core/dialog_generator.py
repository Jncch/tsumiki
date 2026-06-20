"""Phase 9c (2026-06-21): 対話ベース評価器生成.

設計 phase9_design §3.3 に対応. ユーザーとの構造化対話で評価器の
**中身** (パラメータ / judge プロンプト / 重み / 厳しさ) を引き出し、
EvaluatorSpec ドラフトを組み立てる.

設計判断:
- 各評価軸のパラメータ Q は `EvalDimension.parameters` 宣言から **動的に生成**.
- 重み付け / 厳しさ / 確認 Q は静的 (`stage3_parameters.yaml`).
- LLM judge 系 (`llm_judge`, `llm_judge_panel`, `llm_judge_pairwise`) のみ
  判定基準を自然言語で受け取り `prompt_template` を埋める.
- 評価器 implementation は **各軸の implementation_template を合成** した
  Python ソースコードとして組み立てる.

Phase 9c のスコープ:
- パラメータ抽出 (extract_dimension_parameters)
- judge 基準抽出 (extract_judge_criteria)
- 重み付け (resolve_weights)
- 厳しさ (resolve_strictness)
- implementation 合成 (build_implementation_source)
- EvaluatorSpec ドラフト構築 (build_evaluator_draft)

Phase 9d 持ち越し:
- サンプル提示 + 判定一致確認
- judge プロンプトの調整ループ
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from tsumiki.goal.specs import (
    EvaluatorSpec,
    EvaluatorType,
    TaskSpec,
)
from tsumiki.knowledge.schemas.eval_dimensions import EvalDimension

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]
JsonChatFn = Callable[[list[dict]], dict]

StrictnessLevel = Literal["strict", "lenient", "balanced"]
WeightsMode = Literal["equal", "custom"]


@dataclass(frozen=True)
class DimensionParameters:
    """1 つの評価軸の確定パラメータ + judge 基準."""

    dimension_id: str
    param_values: dict[str, Any]  # implementation_template に埋める値
    judge_criteria: str = ""      # LLM judge 系のみ. それ以外は空文字


@dataclass(frozen=True)
class EvaluatorDraft:
    """対話で組み立てた評価器ドラフト. Stage 6 承認後に EvaluatorSpec として保存."""

    task_spec: TaskSpec
    dimensions: tuple[DimensionParameters, ...]
    weights: dict[str, float]  # dimension_id -> weight (0.0〜1.0, 合計 1.0)
    strictness: StrictnessLevel
    implementation_source: str
    evaluator_type: EvaluatorType
    guardrails: tuple[str, ...]


def extract_dimension_parameters(
    dimension: EvalDimension,
    raw_goal: str,
    input_fn: InputFn,
    output_fn: OutputFn,
    json_chat_fn: JsonChatFn | None = None,
) -> DimensionParameters:
    """1 つの評価軸についてパラメータ + judge 基準を対話で取得.

    動的 Q を生成: dimension.parameters の各エントリを順次質問する.
    LLM judge 系は加えて「判定基準」を自由テキストで受け取る.
    """
    output_fn(f"  --- 軸 [{dimension.id}] {dimension.label} のパラメータ設定 ---")
    param_values: dict[str, Any] = {}
    for param in dimension.parameters:
        default_str = (
            f" [default={param.default!r}]" if param.default is not None else ""
        )
        required_str = " (必須)" if param.required else " (任意)"
        prompt = f"    {param.name}{required_str}{default_str}: "
        if param.description:
            output_fn(f"    ({param.description})")
        output_fn(prompt)
        ans = input_fn(f"{dimension.id}__{param.name}").strip()
        if not ans:
            if param.required and param.default is None:
                raise ValueError(
                    f"軸 {dimension.id!r} のパラメータ {param.name!r} は必須です"
                )
            param_values[param.name] = param.default
        else:
            param_values[param.name] = _coerce_value(ans, param.type)

    # LLM judge 系のみ判定基準を聞く
    judge_criteria = ""
    if dimension.type in ("llm_judge", "llm_judge_panel", "llm_judge_pairwise"):
        output_fn(f"    判定基準を自然言語で記述してください ({dimension.id})")
        if json_chat_fn is not None and raw_goal:
            output_fn("    (空 Enter で LLM 提案を求めます)")
        judge_criteria = input_fn(f"{dimension.id}__judge_criteria").strip()
        if not judge_criteria and json_chat_fn is not None:
            judge_criteria = _suggest_judge_criteria(
                dimension, raw_goal, json_chat_fn
            )
            if judge_criteria:
                output_fn(f"    [LLM 提案] {judge_criteria}")
                edit = input_fn(f"{dimension.id}__judge_criteria__edit").strip()
                if edit:
                    judge_criteria = edit

    return DimensionParameters(
        dimension_id=dimension.id,
        param_values=param_values,
        judge_criteria=judge_criteria,
    )


def _coerce_value(raw: str, type_hint: str) -> Any:
    """文字列入力をパラメータ型に変換. 失敗時は raw のまま返す."""
    t = type_hint.lower()
    try:
        if t == "int":
            return int(raw)
        if t in ("float", "number"):
            return float(raw)
        if t == "bool":
            return raw.lower() in ("true", "yes", "y", "1")
        if t == "list":
            # カンマ区切りで分割
            return [s.strip() for s in raw.split(",") if s.strip()]
    except ValueError:
        pass
    return raw


def _suggest_judge_criteria(
    dimension: EvalDimension,
    raw_goal: str,
    json_chat_fn: JsonChatFn,
) -> str:
    """LLM judge 軸の判定基準を LLM に提案させる."""
    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "tsumiki 対話 REPL の補助 LLM. ユーザーの目的と評価軸の説明から、"
                    "LLM judge の判定基準を 1 文 (50〜120 字) で提案する. "
                    'JSON 形式で {"criteria": "<text>"} と返す.'
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "raw_goal": raw_goal,
                        "dimension_id": dimension.id,
                        "dimension_label": dimension.label,
                        "dimension_description": dimension.description,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        result = json_chat_fn(messages)
        return str(result.get("criteria", "")).strip()
    except Exception:
        return ""


def resolve_weights(
    dimensions: tuple[DimensionParameters, ...],
    mode: WeightsMode,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> dict[str, float]:
    """重み付けを確定. equal=均等、custom=各軸を Q で聞く."""
    n = len(dimensions)
    if n == 0:
        return {}
    if mode == "equal":
        return {d.dimension_id: 1.0 / n for d in dimensions}

    output_fn("  --- 軸の重み付け (0.0〜1.0, 合計が 1.0 になるよう自動正規化) ---")
    raw_weights: dict[str, float] = {}
    for d in dimensions:
        prompt = f"    {d.dimension_id} の重み: "
        output_fn(prompt)
        ans = input_fn(f"{d.dimension_id}__weight").strip()
        try:
            raw_weights[d.dimension_id] = float(ans) if ans else 1.0
        except ValueError as e:
            raise ValueError(
                f"軸 {d.dimension_id!r} の重みが数値ではありません: {ans!r}"
            ) from e
    total = sum(raw_weights.values())
    if total <= 0:
        raise ValueError("重みの合計が 0 以下です")
    return {k: v / total for k, v in raw_weights.items()}


def resolve_strictness_guardrails(
    strictness: StrictnessLevel,
    dimensions: tuple[DimensionParameters, ...],
    dimension_specs: dict[str, EvalDimension],
) -> tuple[str, ...]:
    """厳しさ + 各軸の guardrails を統合した guardrails tuple を返す."""
    base = (f"strictness:{strictness}",)
    per_dim: list[str] = []
    for dp in dimensions:
        spec = dimension_specs.get(dp.dimension_id)
        if spec is not None:
            per_dim.extend(spec.guardrails)
    return base + tuple(sorted(set(per_dim)))


def build_implementation_source(
    dimensions: tuple[DimensionParameters, ...],
    dimension_specs: dict[str, EvalDimension],
    weights: dict[str, float],
    strictness: StrictnessLevel,
) -> str:
    """各軸の implementation_template + prompt_template を埋め込み、合算する Python ソース."""
    parts: list[str] = []
    parts.append("# Auto-generated evaluator (Phase 9c dialog_generator).")
    parts.append("# 各軸の implementation_template + prompt_template を埋め込み、")
    parts.append("# weights / strictness に従って合算する.")
    parts.append("")
    parts.append("def _strictness_pass_threshold(strictness: str) -> float:")
    parts.append("    return {'strict': 0.9, 'balanced': 0.7, 'lenient': 0.5}[strictness]")
    parts.append("")
    parts.append("def evaluate(payload: dict) -> dict:")
    parts.append(f"    strictness = {strictness!r}")
    parts.append(f"    weights = {weights!r}")
    parts.append("    per_dim_scores: dict[str, float] = {}")
    parts.append("    per_dim_details: dict[str, dict] = {}")
    parts.append("")
    for dp in dimensions:
        spec = dimension_specs.get(dp.dimension_id)
        if spec is None:
            continue
        parts.append(f"    # === 軸: {dp.dimension_id} ({spec.type}) ===")
        if spec.type == "deterministic" and spec.implementation_template:
            try:
                inner = spec.implementation_template.format(**dp.param_values)
            except KeyError as e:
                raise ValueError(
                    f"軸 {dp.dimension_id!r} の implementation_template に "
                    f"未指定パラメータ {e!s}"
                ) from e
            parts.append(_indent_block(inner, 4))
            parts.append("    res = evaluate(payload.get('output', ''))")
            parts.append(f"    per_dim_scores[{dp.dimension_id!r}] = res['score']")
            parts.append(f"    per_dim_details[{dp.dimension_id!r}] = res")
        elif spec.type in ("llm_judge", "llm_judge_panel", "llm_judge_pairwise"):
            # judge プロンプトを criteria で埋めた文字列を変数として保持
            prompt = (spec.prompt_template or "").format(
                criteria=dp.judge_criteria,
                **{k: f"{{{k}}}" for k in ("output", "target_label", "target_text", "output_a", "output_b")},
            )
            prompt_lines = prompt.splitlines() or [""]
            parts.append(f"    {dp.dimension_id}__prompt = (")
            for line in prompt_lines:
                parts.append(f"        {line!r}")
            parts.append("    )")
            parts.append(
                "    # NOTE: LLM judge の実行は runner 側で chat_fn を注入して行う."
            )
            parts.append(
                f"    per_dim_scores[{dp.dimension_id!r}] = "
                "payload.get('judge_scores', {}).get("
                f"{dp.dimension_id!r}, 0.0)"
            )
            parts.append(
                f"    per_dim_details[{dp.dimension_id!r}] = "
                "{'prompt': " + f"{dp.dimension_id}__prompt" + ", "
                f"'criteria': {dp.judge_criteria!r}" + "}"
            )
        parts.append("")
    parts.append("    weighted_score = sum(per_dim_scores.get(k, 0.0) * w for k, w in weights.items())")
    parts.append("    passed = weighted_score >= _strictness_pass_threshold(strictness)")
    parts.append("    return {")
    parts.append("        'score': weighted_score,")
    parts.append("        'passed': passed,")
    parts.append("        'per_dimension': per_dim_details,")
    parts.append("        'per_dimension_score': per_dim_scores,")
    parts.append("    }")
    return "\n".join(parts)


def _indent_block(block: str, n: int) -> str:
    """テキストブロック全体を n スペースインデント."""
    prefix = " " * n
    return "\n".join(prefix + line if line else line for line in block.splitlines())


def _infer_evaluator_type(dimensions: tuple[DimensionParameters, ...], dimension_specs: dict[str, EvalDimension]) -> EvaluatorType:
    """軸の type 構成から EvaluatorSpec.type を推論."""
    types = {dimension_specs[d.dimension_id].type for d in dimensions if d.dimension_id in dimension_specs}
    if not types:
        return "deterministic"
    if types == {"deterministic"}:
        return "deterministic"
    if types <= {"llm_judge", "llm_judge_panel", "llm_judge_pairwise"}:
        return "llm_judge"
    return "hybrid"


def build_evaluator_draft(
    task_spec: TaskSpec,
    dimensions: tuple[DimensionParameters, ...],
    dimension_specs: dict[str, EvalDimension],
    weights: dict[str, float],
    strictness: StrictnessLevel,
) -> EvaluatorDraft:
    """各要素から EvaluatorDraft (まだ EvaluatorSpec ではない) を構築."""
    impl_source = build_implementation_source(
        dimensions, dimension_specs, weights, strictness
    )
    eval_type = _infer_evaluator_type(dimensions, dimension_specs)
    guardrails = resolve_strictness_guardrails(strictness, dimensions, dimension_specs)
    return EvaluatorDraft(
        task_spec=task_spec,
        dimensions=dimensions,
        weights=weights,
        strictness=strictness,
        implementation_source=impl_source,
        evaluator_type=eval_type,
        guardrails=guardrails,
    )


def draft_to_evaluator_spec(
    draft: EvaluatorDraft,
    evaluator_id: str,
    generated_at: str,
    approved_by: str = "",
) -> EvaluatorSpec:
    """ドラフトから EvaluatorSpec を作成 (まだ approved_by は空のまま許容).

    test_cases は Phase 9d (sample 提示 + 判定一致確認) で詰める想定. ここでは空.
    """
    return EvaluatorSpec(
        id=evaluator_id,
        domain=draft.task_spec.domain,
        task_class=draft.task_spec.task_class,
        type=draft.evaluator_type,
        input_signature=draft.task_spec.io_signature(),
        output_metrics=tuple(f"score_{d.dimension_id}" for d in draft.dimensions) + ("score",),
        implementation=draft.implementation_source,
        test_cases=(),
        guardrails=draft.guardrails,
        sources=tuple(d.dimension_id for d in draft.dimensions),
        generated_at=generated_at,
        approved_by=approved_by,
        notes=(
            f"weights={draft.weights}, strictness={draft.strictness}, "
            f"generated_via=dialog_generator_phase9c"
        ),
        output_kind=draft.task_spec.output_kind,
    )


__all__ = [
    "DimensionParameters",
    "EvaluatorDraft",
    "StrictnessLevel",
    "WeightsMode",
    "build_evaluator_draft",
    "build_implementation_source",
    "draft_to_evaluator_spec",
    "extract_dimension_parameters",
    "resolve_strictness_guardrails",
    "resolve_weights",
]
