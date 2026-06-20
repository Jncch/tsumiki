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


@dataclass
class DialogState:
    """対話の現在状態. 各 stage 関数が書き換える."""

    raw_goal: str = ""
    answers: dict[str, str] = field(default_factory=dict)  # Q ID -> 回答
    task_spec: TaskSpec | None = None
    candidate_dimensions: tuple[EvalDimension, ...] = ()
    selected_dimensions: tuple[EvalDimension, ...] = ()
    eval_spec_draft: dict | None = None  # Phase 9c で本実装
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
    """評価器コード案の提示 + ユーザー確認.

    Phase 9c で本実装. 9b では「軸の組合せ確認」だけ.
    """
    if not state.selected_dimensions:
        output_fn("=== Stage 3: 評価器ドラフト (軸未選択のためスキップ) ===")
        return state
    output_fn("=== Stage 3: 評価器ドラフト (Phase 9c で本実装) ===")
    output_fn(f"  選択軸: {[d.id for d in state.selected_dimensions]}")
    state.eval_spec_draft = {
        "dimensions": [d.id for d in state.selected_dimensions],
        "draft_note": "Phase 9c で本実装. 現状は軸 ID のリストのみ.",
    }
    _log(state, "stage3_draft_evaluator", state.eval_spec_draft, config.timestamp_fn())
    return state


def stage4_sample_judgment(
    state: DialogState,
    config: DialogConfig,
    json_chat_fn: JsonChatFn | None,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> DialogState:
    """サンプル提示 + 判定一致確認. Phase 9d で本実装."""
    output_fn("=== Stage 4: サンプル判定一致確認 (Phase 9d で本実装) ===")
    _log(state, "stage4_sample_judgment", {"deferred": "phase9d"}, config.timestamp_fn())
    return state


def stage5_adjust_judge(
    state: DialogState,
    config: DialogConfig,
    json_chat_fn: JsonChatFn | None,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> DialogState:
    """judge プロンプト調整ループ. Phase 9d で本実装."""
    output_fn("=== Stage 5: judge 調整 (Phase 9d で本実装) ===")
    _log(state, "stage5_adjust_judge", {"deferred": "phase9d"}, config.timestamp_fn())
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
