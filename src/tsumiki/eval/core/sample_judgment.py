"""Phase 9d (2026-06-21): サンプル生成 + システム判定 + ユーザー判定 + 不一致集計.

設計 phase9_design §3.4 に対応. 「対話で得る情報の量と質が評価器精度を上げる」原則に従い、
ユーザーと協調して評価器ドラフトを較正するための API.

設計判断:
- サンプル生成は強モデル必須だが Phase 9d は DI 化 (chat_fn を引数化) で
  テスト時は scripted で代用可能.
- system 判定は **deterministic 軸のみ** で評価. LLM judge 軸は Phase 9e の
  runner が chat_fn を注入して評価する想定なので、ここではスコア未確定扱い.
- 不一致集計は user_passed vs system_passed の食い違いを Disagreement として返す.
  どの判定が「正」かは決めず、後の調整 (Stage 5) の入力にする.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from tsumiki.eval.core.dialog_generator import EvaluatorDraft
from tsumiki.goal.specs import TaskSpec
from tsumiki.knowledge.schemas.eval_dimensions import EvalDimension

JsonChatFn = Callable[[list[dict]], dict]


@dataclass(frozen=True)
class Sample:
    """評価対象のサンプル 1 件."""

    id: str
    output: str  # 評価器の評価対象 (生成された原稿、要約、判断等)
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SystemJudgment:
    """評価器ドラフトによる system 判定."""

    sample_id: str
    score: float
    passed: bool
    per_dim_scores: dict[str, float]  # deterministic 軸のみ. LLM judge 軸は欠落
    pending_dim_ids: tuple[str, ...]  # 評価未確定の軸 (LLM judge 系)


@dataclass(frozen=True)
class UserJudgment:
    """ユーザーによる判定."""

    sample_id: str
    passed: bool


@dataclass(frozen=True)
class Disagreement:
    """system と user の判定不一致 1 件."""

    sample_id: str
    system_passed: bool
    user_passed: bool
    pending_dim_ids: tuple[str, ...]  # 「これらの軸が原因の可能性」


def generate_samples(
    task_spec: TaskSpec,
    count: int,
    json_chat_fn: JsonChatFn,
) -> tuple[Sample, ...]:
    """task_spec から N 件のサンプル output を生成.

    JSON 形式 {"samples": [{"id": "s1", "output": "..."}, ...]} を期待.
    失敗時は空 tuple を返す (Stage 4 でフォールバック処理).
    """
    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "tsumiki 対話 REPL の補助 LLM. ユーザーの task_spec に従い、"
                    f"評価対象となるサンプルを {count} 件生成する. "
                    "良いサンプルと悪いサンプルが混在するよう多様性を持たせる. "
                    'JSON で {"samples": [{"id": "<short id>", "output": "<text>"}, ...]} を返す.'
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "raw_goal": task_spec.raw_goal,
                        "task_class": task_spec.task_class,
                        "output_kind": task_spec.output_kind,
                        "input_modality": task_spec.input_modality,
                        "domain": task_spec.domain,
                        "count": count,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        result = json_chat_fn(messages)
        raw_samples = result.get("samples", []) or []
        samples = []
        for raw in raw_samples[:count]:
            sid = str(raw.get("id", "")) or f"s{len(samples) + 1}"
            output = str(raw.get("output", ""))
            samples.append(Sample(id=sid, output=output))
        return tuple(samples)
    except Exception:
        return ()


def _is_deterministic(dim: EvalDimension) -> bool:
    return dim.type == "deterministic"


def judge_samples_with_draft(
    samples: tuple[Sample, ...],
    draft: EvaluatorDraft,
    dimension_specs: dict[str, EvalDimension],
) -> tuple[SystemJudgment, ...]:
    """各サンプルを deterministic 軸のみで評価し SystemJudgment を返す.

    LLM judge 軸 (llm_judge / llm_judge_panel / llm_judge_pairwise) は
    Phase 9e の runner が評価する想定なので, ここではスコア未確定として保留.
    deterministic 軸のスコアと重みから加重スコアを算出し, strictness しきい値で
    暫定 passed を返す.

    runner ではないため build_implementation_source の合成コードは exec しない.
    各軸の implementation_template を template 展開 + 個別 exec する.
    """
    thresholds = {"strict": 0.9, "balanced": 0.7, "lenient": 0.5}
    threshold = thresholds[draft.strictness]
    judgments = []
    for sample in samples:
        per_dim_scores: dict[str, float] = {}
        pending: list[str] = []
        for dp in draft.dimensions:
            spec = dimension_specs.get(dp.dimension_id)
            if spec is None:
                pending.append(dp.dimension_id)
                continue
            if not _is_deterministic(spec):
                pending.append(dp.dimension_id)
                continue
            if spec.implementation_template is None:
                pending.append(dp.dimension_id)
                continue
            try:
                impl = spec.implementation_template.format(**dp.param_values)
            except KeyError:
                pending.append(dp.dimension_id)
                continue
            scope: dict = {}
            try:
                exec(impl, scope)  # noqa: S102 — vendored template exec by design
                evaluate = scope.get("evaluate")
                if not callable(evaluate):
                    pending.append(dp.dimension_id)
                    continue
                result = evaluate(sample.output)
                per_dim_scores[dp.dimension_id] = float(result.get("score", 0.0))
            except Exception:
                pending.append(dp.dimension_id)
        # 加重スコアは「採点済み軸の重みでのみ正規化」して算出する.
        weights = draft.weights
        scored_weight = sum(
            weights.get(k, 0.0) for k in per_dim_scores.keys()
        )
        if scored_weight <= 0:
            weighted_score = 0.0
            passed_flag = False
        else:
            weighted_score = (
                sum(per_dim_scores[k] * weights.get(k, 0.0) for k in per_dim_scores)
                / scored_weight
            )
            passed_flag = weighted_score >= threshold
        judgments.append(
            SystemJudgment(
                sample_id=sample.id,
                score=weighted_score,
                passed=passed_flag,
                per_dim_scores=per_dim_scores,
                pending_dim_ids=tuple(pending),
            )
        )
    return tuple(judgments)


def compute_disagreements(
    system_judgments: tuple[SystemJudgment, ...],
    user_judgments: tuple[UserJudgment, ...],
) -> tuple[Disagreement, ...]:
    """system と user の判定不一致を抽出."""
    user_map = {u.sample_id: u for u in user_judgments}
    out = []
    for sj in system_judgments:
        uj = user_map.get(sj.sample_id)
        if uj is None:
            continue
        if sj.passed != uj.passed:
            out.append(
                Disagreement(
                    sample_id=sj.sample_id,
                    system_passed=sj.passed,
                    user_passed=uj.passed,
                    pending_dim_ids=sj.pending_dim_ids,
                )
            )
    return tuple(out)


__all__ = [
    "Disagreement",
    "JsonChatFn",
    "Sample",
    "SystemJudgment",
    "UserJudgment",
    "compute_disagreements",
    "generate_samples",
    "judge_samples_with_draft",
]
