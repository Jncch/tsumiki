"""Phase 9b: 対話 REPL — 構造化質問 + LLM デフォルト提案ハイブリッド.

設計 phase9_design §3.2 に対応. 「無数のユースケースに対応する評価器の生成手法」を
ユーザーとの構造化対話で組み立てるためのコア.

設計判断:
- 主軸は **構造化質問** (Q1, Q2, ... の固定リスト). Phase 8-6 で観測した
  「LLM parser の文言揺れ → input_signature 不一致 → lookup miss」を回避する.
- LLM は **回答が空のときだけデフォルト提案** する補助役.
- 6 stage 構造のうち Phase 9b では stage 1 (TaskSpec 確定), stage 2 (評価軸選択),
  stage 6 (承認) を実装. stage 3-5 (評価器 draft + sample 判定) は Phase 9c/9d で.

Phase 9b 改訂 (2026-06-20):
- Q1〜Q10 の質問定義を `knowledge/schemas/dialog_questions/_common/*.yaml` に外部化.
- dialog.py は loader 経由で質問を取得する形に変更.
- ドメイン固有質問は `<domain>/<stage>*.yaml` で _common を override 可能.

I/O 抽象化:
- input_fn(prompt) -> user_answer  ←  builtin input() / scripted iterator
- output_fn(message) -> None       ←  print() / list 蓄積
- json_chat_fn(messages) -> dict   ←  LLM 提案用 (None でも動作可)
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from tsumiki.eval.core.dialog_generator import (
    DimensionParameters,
    EvaluatorDraft,
    StrictnessLevel,
    build_evaluator_draft,
    extract_dimension_parameters,
    resolve_weights,
)
from tsumiki.eval.core.judge_adjuster import (
    apply_criteria_revisions,
    collect_judge_dimension_ids,
    suggest_criteria_revision,
)
from tsumiki.eval.core.sample_judgment import (
    Disagreement,
    Sample,
    UserJudgment,
    compute_disagreements,
    generate_samples,
    judge_samples_with_draft,
)
from tsumiki.goal.specs import (
    InputRole,
    KnowledgeSource,
    OutputSchema,
    TaskSpec,
)
from tsumiki.knowledge.schemas.dialog_questions import (
    DialogQuestion,
    DialogQuestionsBundle,
    load_all_dialog_questions,
    load_dialog_questions,
)
from tsumiki.knowledge.schemas.eval_dimensions import (
    EvalDimension,
    filter_applicable,
    load_eval_dimensions,
)

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]
JsonChatFn = Callable[[list[dict]], dict]
TimestampFn = Callable[[], str]


DEFAULT_QUESTIONS_ROOT = (
    Path(__file__).parent.parent / "knowledge" / "schemas" / "dialog_questions"
)
DEFAULT_DIMENSIONS_ROOT = (
    Path(__file__).parent.parent / "knowledge" / "schemas" / "eval_dimensions"
)


def _utc_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class DialogConfig:
    """対話のパラメータ.

    questions_root と dimensions_root は YAML テンプレのルート.
    どちらも `_common/` を必須とし `<domain>/` で override 可能 (Phase 9b 改訂).
    """

    log_dir: Path
    dimensions_root: Path = field(default_factory=lambda: DEFAULT_DIMENSIONS_ROOT)
    questions_root: Path = field(default_factory=lambda: DEFAULT_QUESTIONS_ROOT)
    timestamp_fn: TimestampFn = _utc_iso
    approve_by_prefix: str = "user_dialog"
    # Phase 9d で追加: Stage 4 で生成するサンプル数 / Stage 5 の最大反復数.
    sample_count: int = 4
    max_judge_adjust_rounds: int = 2


@dataclass
class DialogState:
    """対話の現在状態. 各 stage 関数が書き換える."""

    raw_goal: str = ""
    answers: dict[str, str] = field(default_factory=dict)  # Q ID -> 回答
    task_spec: TaskSpec | None = None
    candidate_dimensions: tuple[EvalDimension, ...] = ()
    selected_dimensions: tuple[EvalDimension, ...] = ()
    # Phase 9c で型を dict から EvaluatorDraft に変更.
    eval_spec_draft: EvaluatorDraft | None = None
    sample_judgments: list[dict] = field(default_factory=list)  # Phase 9d
    approved: bool = False
    approved_by: str = ""
    log_entries: list[dict] = field(default_factory=list)


def _log(state: DialogState, stage: str, payload: dict, ts: str) -> None:
    state.log_entries.append({"stage": stage, "payload": payload, "timestamp": ts})


def _ask(
    question: DialogQuestion,
    state: DialogState,
    json_chat_fn: JsonChatFn | None,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> str:
    """1 つの Q を提示し回答を取得. 空回答時に LLM 提案を行う."""
    output_fn(question.prompt)
    if question.allowed_values:
        output_fn(f"  選択肢: {', '.join(question.allowed_values)}")
    answer = input_fn(question.id).strip()

    if not answer and question.llm_suggest and json_chat_fn is not None:
        suggestion = _llm_suggest(question, state, json_chat_fn)
        if suggestion:
            output_fn(f"  [LLM 提案] {suggestion} (Enter で採用、または再入力)")
            answer = input_fn(question.id + "__after_suggest").strip() or suggestion
        else:
            output_fn("  [LLM 提案なし - 再度入力してください]")
            answer = input_fn(question.id + "__no_suggest").strip()

    if question.expected_type == "literal" and question.allowed_values:
        if answer not in question.allowed_values:
            raise ValueError(
                f"{question.id} に許可されない値: {answer!r} "
                f"(allowed: {question.allowed_values})"
            )
    if question.expected_type == "yes_no":
        if answer.lower() not in ("yes", "no", "y", "n"):
            raise ValueError(f"{question.id} は yes/no で答えてください: {answer!r}")
    return answer


def _llm_suggest(
    question: DialogQuestion,
    state: DialogState,
    json_chat_fn: JsonChatFn,
) -> str:
    """質問に対する LLM デフォルト提案を取る. 失敗時は空文字."""
    try:
        context = {"raw_goal": state.raw_goal, "answers_so_far": state.answers}
        messages = [
            {
                "role": "system",
                "content": (
                    "tsumiki 対話 REPL の補助 LLM. 質問に対する最も妥当な 1 つの選択肢を"
                    ' JSON で {"suggestion": "<value>"} 形式で返す. 選択肢が指定されて'
                    "いる場合は必ずその中から選ぶ."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question.prompt,
                        "allowed_values": list(question.allowed_values),
                        "context": context,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        result = json_chat_fn(messages)
        suggestion = str(result.get("suggestion", "")).strip()
        if question.allowed_values and suggestion not in question.allowed_values:
            return ""
        return suggestion
    except Exception:
        return ""


def _parse_input_roles(csv: str) -> tuple[InputRole, ...]:
    """'name1:role1,name2:role2' を InputRole の tuple に変換."""
    if not csv.strip():
        return ()
    roles = []
    for chunk in csv.split(","):
        if ":" not in chunk:
            raise ValueError(f"input_roles 形式エラー: {chunk!r} (name:role_kind を期待)")
        name, role = chunk.strip().split(":", 1)
        roles.append(
            InputRole(
                name=name.strip(),
                formats=("md",),  # default. Phase 9c で formats も対話で取る
                role=role.strip(),  # type: ignore[arg-type]
            )
        )
    return tuple(roles)


def _parse_outputs(csv: str) -> tuple[OutputSchema, ...]:
    """'name1:schema_id1,name2:schema_id2' を OutputSchema の tuple に変換."""
    if not csv.strip():
        return ()
    outs = []
    for chunk in csv.split(","):
        if ":" not in chunk:
            raise ValueError(f"outputs 形式エラー: {chunk!r} (name:schema_id を期待)")
        name, schema_id = chunk.strip().split(":", 1)
        outs.append(OutputSchema(name=name.strip(), schema_id=schema_id.strip()))
    return tuple(outs)


def _load_questions(config: DialogConfig, domain: str | None = None) -> DialogQuestionsBundle:
    """YAML から全 stage の質問を取得."""
    return load_all_dialog_questions(config.questions_root, domain)


def stage1_clarify_goal(
    state: DialogState,
    config: DialogConfig,
    json_chat_fn: JsonChatFn | None,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> DialogState:
    """Q1〜Q8 (stage1 YAML 定義分) で TaskSpec を確定."""
    output_fn("=== Stage 1: 目的と TaskSpec の確定 ===")
    # ドメインは Q5 で確定するため Stage 1 では _common のみロード.
    bundle = _load_questions(config, domain=None)
    for q in bundle.task_spec.questions:
        ans = _ask(q, state, json_chat_fn, input_fn, output_fn)
        state.answers[q.id] = ans
        if q.id == "raw_goal":
            state.raw_goal = ans

    catalog_path = state.answers.get("knowledge_catalog_path", "").strip()
    knowledge = KnowledgeSource(
        source_type="existing" if catalog_path else "extract",
        catalog_path=catalog_path or None,
    )
    task_spec = TaskSpec(
        task_class=state.answers["task_class"],  # type: ignore[arg-type]
        domain=state.answers["domain"],
        input_roles=_parse_input_roles(state.answers["input_roles_csv"]),
        knowledge=knowledge,
        outputs=_parse_outputs(state.answers["outputs_csv"]),
        raw_goal=state.raw_goal,
        output_kind=state.answers["output_kind"],  # type: ignore[arg-type]
        input_modality=state.answers["input_modality"],  # type: ignore[arg-type]
    )
    state.task_spec = task_spec
    _log(
        state,
        "stage1_clarify_goal",
        {
            "task_spec_summary": {
                "task_class": task_spec.task_class,
                "domain": task_spec.domain,
                "output_kind": task_spec.output_kind,
                "input_modality": task_spec.input_modality,
            }
        },
        config.timestamp_fn(),
    )
    output_fn(
        f"  → TaskSpec 確定: {task_spec.domain} / {task_spec.task_class} / "
        f"{task_spec.output_kind} / {task_spec.input_modality}"
    )
    return state


def stage2_select_dimensions(
    state: DialogState,
    config: DialogConfig,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> DialogState:
    """評価軸候補を提示 → ユーザー選択 (Q9 = stage2 YAML 定義)."""
    if state.task_spec is None:
        raise RuntimeError("stage1 を先に通してください")
    output_fn("=== Stage 2: 評価軸の選択 ===")

    dims = load_eval_dimensions(config.dimensions_root, state.task_spec.domain)
    applicable = filter_applicable(
        dims, state.task_spec.task_class, state.task_spec.output_kind
    )
    state.candidate_dimensions = applicable

    # ドメイン確定後に Q9 をドメイン固有テンプレで上書き可能.
    bundle = _load_questions(config, domain=state.task_spec.domain)

    if not applicable:
        output_fn(
            f"  警告: task_class={state.task_spec.task_class}, output_kind={state.task_spec.output_kind} "
            f"に適用可能な評価軸が _common にも {state.task_spec.domain}/ にも見つかりません. "
            "Phase 9c で評価軸を自動生成する経路に進みます (現状は β)"
        )
        _log(
            state,
            "stage2_select_dimensions",
            {"candidates": [], "selected": []},
            config.timestamp_fn(),
        )
        return state

    output_fn("  適用可能な評価軸:")
    for d in applicable:
        output_fn(f"    [{d.id}] {d.label} ({d.type}, source={d.source_domain})")

    q = bundle.dimensions.questions[0]
    ans = input_fn(q.id).strip()
    selected_ids = [s.strip() for s in ans.split(",") if s.strip()]
    by_id = {d.id: d for d in applicable}
    missing = [s for s in selected_ids if s not in by_id]
    if missing:
        raise ValueError(f"未知の評価軸 ID: {missing}")
    state.selected_dimensions = tuple(by_id[s] for s in selected_ids)
    state.answers[q.id] = ans
    _log(
        state,
        "stage2_select_dimensions",
        {"candidates": [d.id for d in applicable], "selected": list(selected_ids)},
        config.timestamp_fn(),
    )
    output_fn(f"  → {len(state.selected_dimensions)} 軸選択: {selected_ids}")
    return state


def stage3_draft_evaluator(
    state: DialogState,
    config: DialogConfig,
    json_chat_fn: JsonChatFn | None,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> DialogState:
    """評価器コード案の提示 + ユーザー確認 (Phase 9c 本実装).

    フロー:
    1. 選択された各評価軸について `EvalDimension.parameters` を動的 Q で抽出
    2. LLM judge 系の軸は加えて判定基準 (criteria) を自然言語で受け取る
    3. 重み付け (Q11: equal/custom) を確定
    4. 厳しさ (Q12: strict/lenient/balanced) を確定
    5. EvaluatorDraft を組み立てユーザーに概要を提示
    6. 確認 (Q13: yes/no) → state.eval_spec_draft に格納
    """
    if state.task_spec is None:
        raise RuntimeError("stage1 を先に通してください")
    if not state.selected_dimensions:
        output_fn("=== Stage 3: 評価器ドラフト (軸未選択のためスキップ) ===")
        return state

    output_fn("=== Stage 3: 評価器ドラフトの組み立て (Phase 9c) ===")
    domain = state.task_spec.domain

    # 1. 各軸のパラメータ + judge 基準を抽出
    dimension_params: list[DimensionParameters] = []
    for dim in state.selected_dimensions:
        params = extract_dimension_parameters(
            dim, state.raw_goal, input_fn, output_fn, json_chat_fn
        )
        dimension_params.append(params)
    dimensions_tuple = tuple(dimension_params)

    # 2. 静的 Q (Q11=重み, Q12=厳しさ, Q13=確認) を YAML からロード
    stage3 = load_dialog_questions(config.questions_root, "stage3", domain=domain)
    q_by_id = {q.id: q for q in stage3.questions}
    q_weights = q_by_id["weights_mode"]
    q_strictness = q_by_id["strictness"]
    q_confirm = q_by_id["evaluator_draft_confirm"]

    # 3. 重み付け
    weights_mode_ans = _ask(q_weights, state, json_chat_fn, input_fn, output_fn)
    state.answers[q_weights.id] = weights_mode_ans
    weights = resolve_weights(
        dimensions_tuple, weights_mode_ans, input_fn, output_fn  # type: ignore[arg-type]
    )

    # 4. 厳しさ
    strictness_ans = _ask(q_strictness, state, json_chat_fn, input_fn, output_fn)
    state.answers[q_strictness.id] = strictness_ans
    strictness: StrictnessLevel = strictness_ans  # type: ignore[assignment]

    # 5. ドラフト組み立て
    dim_spec_map = {d.id: d for d in state.selected_dimensions}
    draft = build_evaluator_draft(
        task_spec=state.task_spec,
        dimensions=dimensions_tuple,
        dimension_specs=dim_spec_map,
        weights=weights,
        strictness=strictness,
    )

    # 6. 概要提示 + 確認
    output_fn("  --- 評価器ドラフト概要 ---")
    output_fn(f"    type: {draft.evaluator_type}")
    output_fn(f"    軸: {[d.dimension_id for d in dimensions_tuple]}")
    output_fn(f"    重み: {draft.weights}")
    output_fn(f"    厳しさ: {draft.strictness}")
    output_fn(f"    guardrails: {list(draft.guardrails)}")
    output_fn(f"    implementation ソース: {len(draft.implementation_source.splitlines())} 行")

    confirm_ans = _ask(q_confirm, state, None, input_fn, output_fn)
    state.answers[q_confirm.id] = confirm_ans
    if confirm_ans.lower() not in ("yes", "y"):
        output_fn("  → ドラフト差し戻し. stage2 から再選択を推奨します")
        state.eval_spec_draft = None
        _log(
            state,
            "stage3_draft_evaluator",
            {"draft_confirmed": False, "answers": {q_weights.id: weights_mode_ans,
                                                   q_strictness.id: strictness_ans}},
            config.timestamp_fn(),
        )
        return state

    state.eval_spec_draft = draft
    _log(
        state,
        "stage3_draft_evaluator",
        {
            "draft_confirmed": True,
            "dimensions": [d.dimension_id for d in dimensions_tuple],
            "weights": weights,
            "strictness": strictness,
            "guardrails": list(draft.guardrails),
            "evaluator_type": draft.evaluator_type,
        },
        config.timestamp_fn(),
    )
    output_fn("  → ドラフト確定")
    return state


def _ask_user_judgments_for_samples(
    samples: tuple[Sample, ...],
    state: DialogState,
    config: DialogConfig,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> tuple[UserJudgment, ...]:
    """各サンプルに対し Q14 を繰り返して UserJudgment を集める."""
    stage4 = load_dialog_questions(config.questions_root, "stage4")
    q_user = next(q for q in stage4.questions if q.id == "user_passed")
    user_judgments: list[UserJudgment] = []
    for sample in samples:
        output_fn(f"  [{sample.id}] {sample.output[:200]}")
        # Q ID をサンプル別にすることでログ重複を回避
        per_sample_q = DialogQuestion(
            id=f"{q_user.id}__{sample.id}",
            prompt=q_user.prompt,
            expected_type=q_user.expected_type,
            allowed_values=q_user.allowed_values,
            description=q_user.description,
            llm_suggest=q_user.llm_suggest,
            validate_against_literal=q_user.validate_against_literal,
        )
        ans = _ask(per_sample_q, state, None, input_fn, output_fn)
        state.answers[per_sample_q.id] = ans
        passed = ans.lower() in ("yes", "y")
        user_judgments.append(UserJudgment(sample_id=sample.id, passed=passed))
    return tuple(user_judgments)


def stage4_sample_judgment(
    state: DialogState,
    config: DialogConfig,
    json_chat_fn: JsonChatFn | None,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> DialogState:
    """サンプル提示 + 判定一致確認 (Phase 9d 本実装).

    1. ドラフトから N 件のサンプルを LLM で生成 (json_chat_fn 必要)
    2. system 判定 (deterministic 軸のみ) を計算
    3. ユーザーに Q14 で各サンプルの判定を聞く
    4. 不一致を state.sample_judgments に記録
    """
    if state.task_spec is None or state.eval_spec_draft is None:
        output_fn("=== Stage 4: サンプル判定 (前提未充足のためスキップ) ===")
        return state

    output_fn("=== Stage 4: サンプル提示 + 判定一致確認 ===")

    # 1. サンプル生成 (LLM 不在ならスキップ)
    if json_chat_fn is None:
        output_fn("  (json_chat_fn が無いためサンプル生成をスキップ)")
        _log(
            state,
            "stage4_sample_judgment",
            {"skipped": "no_json_chat_fn"},
            config.timestamp_fn(),
        )
        return state

    samples = generate_samples(
        state.task_spec, config.sample_count, json_chat_fn
    )
    if not samples:
        output_fn("  警告: サンプル生成に失敗. Stage 4 をスキップ")
        _log(
            state,
            "stage4_sample_judgment",
            {"skipped": "generate_samples_failed"},
            config.timestamp_fn(),
        )
        return state

    # 2. system 判定
    dim_specs = {d.id: d for d in state.selected_dimensions}
    system_judgments = judge_samples_with_draft(samples, state.eval_spec_draft, dim_specs)

    output_fn(f"  {len(samples)} 件のサンプルを生成・採点しました:")
    for sj in system_judgments:
        verdict = "PASS" if sj.passed else "FAIL"
        pending = f" (未確定軸: {list(sj.pending_dim_ids)})" if sj.pending_dim_ids else ""
        output_fn(f"    [{sj.sample_id}] system={verdict} score={sj.score:.3f}{pending}")

    # 3. ユーザー判定
    user_judgments = _ask_user_judgments_for_samples(
        samples, state, config, input_fn, output_fn
    )

    # 4. 不一致集計
    disagreements = compute_disagreements(system_judgments, user_judgments)
    state.sample_judgments.append({
        "samples": [{"id": s.id, "output": s.output} for s in samples],
        "system_judgments": [
            {
                "sample_id": sj.sample_id,
                "passed": sj.passed,
                "score": sj.score,
                "per_dim_scores": sj.per_dim_scores,
                "pending_dim_ids": list(sj.pending_dim_ids),
            }
            for sj in system_judgments
        ],
        "user_judgments": [
            {"sample_id": uj.sample_id, "passed": uj.passed} for uj in user_judgments
        ],
        "disagreements": [
            {
                "sample_id": d.sample_id,
                "system_passed": d.system_passed,
                "user_passed": d.user_passed,
                "pending_dim_ids": list(d.pending_dim_ids),
            }
            for d in disagreements
        ],
    })
    output_fn(f"  → 不一致 {len(disagreements)} 件")
    _log(
        state,
        "stage4_sample_judgment",
        {
            "sample_count": len(samples),
            "disagreement_count": len(disagreements),
        },
        config.timestamp_fn(),
    )
    return state


def stage5_adjust_judge(
    state: DialogState,
    config: DialogConfig,
    json_chat_fn: JsonChatFn | None,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> DialogState:
    """judge プロンプト調整ループ (Phase 9d 本実装).

    1. Stage 4 で記録された不一致を確認
    2. 不一致あり + LLM judge 軸ありなら Q15 で修正するか聞く
    3. yes なら Q16 で対象軸を選び、各軸の新しい criteria を Q17 で取得
    4. apply_criteria_revisions でドラフト更新
    最大 config.max_judge_adjust_rounds 回まで.

    本フェーズでは「1 回だけ修正案を適用する」までを実装. ループは Phase 9e で
    Stage 4 ↔ Stage 5 を組み合わせる際に runner 側で制御する.
    """
    if state.eval_spec_draft is None or not state.sample_judgments:
        output_fn("=== Stage 5: judge 調整 (前提未充足のためスキップ) ===")
        _log(
            state,
            "stage5_adjust_judge",
            {"skipped": "no_draft_or_no_sample_judgments"},
            config.timestamp_fn(),
        )
        return state

    last_round = state.sample_judgments[-1]
    disagreements: tuple[Disagreement, ...] = tuple(
        Disagreement(
            sample_id=d["sample_id"],
            system_passed=d["system_passed"],
            user_passed=d["user_passed"],
            pending_dim_ids=tuple(d["pending_dim_ids"]),
        )
        for d in last_round.get("disagreements", [])
    )
    if not disagreements:
        output_fn("=== Stage 5: judge 調整 (不一致なし、スキップ) ===")
        _log(
            state,
            "stage5_adjust_judge",
            {"skipped": "no_disagreements"},
            config.timestamp_fn(),
        )
        return state

    dim_specs = {d.id: d for d in state.selected_dimensions}
    judge_dim_ids = collect_judge_dimension_ids(state.eval_spec_draft, dim_specs)
    if not judge_dim_ids:
        output_fn("=== Stage 5: judge 調整 (LLM judge 軸なし、スキップ) ===")
        _log(
            state,
            "stage5_adjust_judge",
            {"skipped": "no_judge_dimensions"},
            config.timestamp_fn(),
        )
        return state

    output_fn(f"=== Stage 5: judge プロンプト調整 ({len(disagreements)} 件の不一致) ===")
    stage5 = load_dialog_questions(config.questions_root, "stage5")
    q_request = next(q for q in stage5.questions if q.id == "adjust_request")
    q_targets = next(q for q in stage5.questions if q.id == "dimensions_to_adjust")
    q_revision = next(q for q in stage5.questions if q.id == "criteria_revision")

    # Q15
    req_ans = _ask(q_request, state, None, input_fn, output_fn)
    state.answers[q_request.id] = req_ans
    if req_ans.lower() not in ("yes", "y"):
        output_fn("  → 修正なし")
        _log(state, "stage5_adjust_judge", {"adjusted": False}, config.timestamp_fn())
        return state

    # Q16
    output_fn(f"  LLM judge 軸: {list(judge_dim_ids)}")
    target_ans = input_fn(q_targets.id).strip()
    state.answers[q_targets.id] = target_ans
    if target_ans.lower() == "all":
        target_ids = list(judge_dim_ids)
    else:
        target_ids = [s.strip() for s in target_ans.split(",") if s.strip()]
    unknown = [t for t in target_ids if t not in judge_dim_ids]
    if unknown:
        raise ValueError(f"未知の judge 軸 ID: {unknown}")

    # Q17: 各軸ごとの criteria 更新
    revisions: dict[str, str] = {}
    current_criteria_map = {
        dp.dimension_id: dp.judge_criteria for dp in state.eval_spec_draft.dimensions
    }
    for tid in target_ids:
        spec = dim_specs[tid]
        current_c = current_criteria_map.get(tid, "")
        output_fn(f"  --- 軸 [{tid}] の修正 (現在: {current_c!r}) ---")
        per_dim_q = DialogQuestion(
            id=f"{q_revision.id}__{tid}",
            prompt=q_revision.prompt,
            expected_type=q_revision.expected_type,
            allowed_values=q_revision.allowed_values,
            description=q_revision.description,
        )
        output_fn(per_dim_q.prompt)
        ans = input_fn(per_dim_q.id).strip()
        state.answers[per_dim_q.id] = ans
        if not ans and json_chat_fn is not None:
            suggested = suggest_criteria_revision(
                spec, current_c, disagreements, state.raw_goal, json_chat_fn
            )
            if suggested:
                output_fn(f"    [LLM 提案] {suggested} (Enter で採用、または編集)")
                edit = input_fn(per_dim_q.id + "__after_suggest").strip()
                ans = edit or suggested
        if ans:
            revisions[tid] = ans

    # ドラフト更新
    if revisions:
        new_draft = apply_criteria_revisions(
            state.eval_spec_draft, dim_specs, revisions
        )
        state.eval_spec_draft = new_draft
        output_fn(f"  → {len(revisions)} 軸の criteria を更新しました")
    else:
        output_fn("  → 修正なし (回答が全て空)")

    _log(
        state,
        "stage5_adjust_judge",
        {"adjusted": True, "revised_dimensions": list(revisions.keys())},
        config.timestamp_fn(),
    )
    return state


def stage6_approve(
    state: DialogState,
    config: DialogConfig,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> DialogState:
    """承認 → approved_by 設定 (Q10 = stage6 YAML 定義)."""
    output_fn("=== Stage 6: 承認 ===")
    domain = state.task_spec.domain if state.task_spec else None
    bundle = _load_questions(config, domain=domain)
    q = bundle.approve.questions[0]
    ans = _ask(q, state, None, input_fn, output_fn)
    state.answers[q.id] = ans
    approved = ans.lower() in ("yes", "y")
    state.approved = approved
    if approved:
        state.approved_by = f"{config.approve_by_prefix}_{config.timestamp_fn()}"
    _log(
        state,
        "stage6_approve",
        {"approved": approved, "approved_by": state.approved_by},
        config.timestamp_fn(),
    )
    output_fn(f"  → 承認: {approved} (approved_by={state.approved_by!r})")
    return state


def persist_log(state: DialogState, config: DialogConfig, run_id: str) -> Path:
    """対話ログを JSONL で persist し path を返す."""
    config.log_dir.mkdir(parents=True, exist_ok=True)
    path = config.log_dir / f"{run_id}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for entry in state.log_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def run_dialog(
    config: DialogConfig,
    json_chat_fn: JsonChatFn | None,
    input_fn: InputFn,
    output_fn: OutputFn,
    run_id: str = "dialog",
) -> DialogState:
    """6 stage 対話 REPL のエントリポイント. 承認済 DialogState を返す."""
    state = DialogState()
    state = stage1_clarify_goal(state, config, json_chat_fn, input_fn, output_fn)
    state = stage2_select_dimensions(state, config, input_fn, output_fn)
    state = stage3_draft_evaluator(state, config, json_chat_fn, input_fn, output_fn)
    state = stage4_sample_judgment(state, config, json_chat_fn, input_fn, output_fn)
    state = stage5_adjust_judge(state, config, json_chat_fn, input_fn, output_fn)
    state = stage6_approve(state, config, input_fn, output_fn)
    persist_log(state, config, run_id)
    return state


__all__ = [
    "DEFAULT_DIMENSIONS_ROOT",
    "DEFAULT_QUESTIONS_ROOT",
    "DialogConfig",
    "DialogQuestion",
    "DialogState",
    "InputFn",
    "JsonChatFn",
    "OutputFn",
    "persist_log",
    "run_dialog",
    "stage1_clarify_goal",
    "stage2_select_dimensions",
    "stage3_draft_evaluator",
    "stage4_sample_judgment",
    "stage5_adjust_judge",
    "stage6_approve",
]
