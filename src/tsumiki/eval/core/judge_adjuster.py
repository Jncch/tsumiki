"""Phase 9d (2026-06-21): judge プロンプト調整ループ.

設計 phase9_design §3.4-3.5 に対応. Disagreement を元に LLM judge 軸の criteria を
ユーザーと対話して修正する.

設計判断:
- LLM 提案は補助役 (Phase 8-6 教訓: parser 文言揺れを避けるため最終確定はユーザーが行う).
- 修正対象軸の絞り込みは Q16 で list 指定 (デフォルト all). 全軸でも個別軸でも可.
- 修正後の EvaluatorDraft は build_implementation_source で再合成 (criteria 部分のみ更新).
"""

from __future__ import annotations

import json
from collections.abc import Callable

from tsumiki.eval.core.dialog_generator import (
    DimensionParameters,
    EvaluatorDraft,
    build_evaluator_draft,
)
from tsumiki.eval.core.sample_judgment import Disagreement
from tsumiki.knowledge.schemas.eval_dimensions import EvalDimension

JsonChatFn = Callable[[list[dict]], dict]


def collect_judge_dimension_ids(
    draft: EvaluatorDraft,
    dimension_specs: dict[str, EvalDimension],
) -> tuple[str, ...]:
    """LLM judge 系 (criteria を持つ) 軸の dimension_id を返す."""
    judge_types = ("llm_judge", "llm_judge_panel", "llm_judge_pairwise")
    return tuple(
        dp.dimension_id
        for dp in draft.dimensions
        if (spec := dimension_specs.get(dp.dimension_id)) is not None
        and spec.type in judge_types
    )


def suggest_criteria_revision(
    dimension: EvalDimension,
    current_criteria: str,
    disagreements: tuple[Disagreement, ...],
    raw_goal: str,
    json_chat_fn: JsonChatFn,
) -> str:
    """LLM に criteria の修正案を提案させる. 失敗時は空文字."""
    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "tsumiki 対話 REPL の補助 LLM. 評価器ドラフトと "
                    "user/system 判定不一致を踏まえて、LLM judge 軸の "
                    "criteria (判定基準) を改善した新しい文を 1 文で提案する. "
                    'JSON で {"criteria": "<text>"} と返す.'
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "raw_goal": raw_goal,
                        "dimension_id": dimension.id,
                        "dimension_label": dimension.label,
                        "current_criteria": current_criteria,
                        "disagreement_count": len(disagreements),
                        "disagreement_summaries": [
                            {
                                "sample_id": d.sample_id,
                                "system_passed": d.system_passed,
                                "user_passed": d.user_passed,
                            }
                            for d in disagreements[:5]
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        result = json_chat_fn(messages)
        return str(result.get("criteria", "")).strip()
    except Exception:
        return ""


def apply_criteria_revisions(
    draft: EvaluatorDraft,
    dimension_specs: dict[str, EvalDimension],
    revisions: dict[str, str],
) -> EvaluatorDraft:
    """指定軸の judge_criteria を更新した新しい EvaluatorDraft を返す.

    implementation_source も build_evaluator_draft 経由で再合成する.
    """
    if not revisions:
        return draft
    updated_dims = []
    for dp in draft.dimensions:
        new_criteria = revisions.get(dp.dimension_id, dp.judge_criteria)
        if new_criteria == dp.judge_criteria:
            updated_dims.append(dp)
        else:
            updated_dims.append(
                DimensionParameters(
                    dimension_id=dp.dimension_id,
                    param_values=dp.param_values,
                    judge_criteria=new_criteria,
                )
            )
    return build_evaluator_draft(
        task_spec=draft.task_spec,
        dimensions=tuple(updated_dims),
        dimension_specs=dimension_specs,
        weights=draft.weights,
        strictness=draft.strictness,
    )


__all__ = [
    "JsonChatFn",
    "apply_criteria_revisions",
    "collect_judge_dimension_ids",
    "suggest_criteria_revision",
]
