"""LLM judge 評価器のガードレール.

CLAUDE.md §7.3 「開放タスクではペアワイズ・複数批評パネル・多様性指標・人手較正を使う」
に対応する最小実装. Q3=B 制約 (LLM judge を含む評価器は最低 1 つのガードレール必須).

Phase 5c では雛形のみ. 本格運用は Phase 6 (ISO27001 で開放系評価器が要件化したとき)
で堅牢化する.

設計: docs/experiments/phase5c_design.md §2 eval/core/
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

ChatFn = Callable[[str], str]


@dataclass(frozen=True)
class PairwiseResult:
    winner: str  # "A" / "B" / "TIE"
    rationale: str


def pairwise(
    chat_fn: ChatFn,
    *,
    candidate_a: str,
    candidate_b: str,
    criterion: str,
) -> PairwiseResult:
    """A / B どちらが criterion に合致するかを LLM に判定させる.

    生の LLM スカラーへの最適化を避けるための最小ガードレール. 報酬ハッキング
    を完全には防げないが、絶対値判定よりは安定する.
    """
    prompt = (
        f"次の 2 つの候補を「{criterion}」の観点で比較し、"
        "A / B / TIE のいずれかを最初の行に大文字で出力してください.\n"
        "2 行目以降に判断の理由を 1〜3 行で記述します.\n"
        "\n候補 A:\n'''\n" + candidate_a + "\n'''\n"
        "\n候補 B:\n'''\n" + candidate_b + "\n'''\n"
    )
    text = chat_fn(prompt).strip()
    first_line = text.splitlines()[0].strip().upper() if text else ""
    if first_line.startswith("A"):
        winner = "A"
    elif first_line.startswith("B"):
        winner = "B"
    else:
        winner = "TIE"
    rationale = "\n".join(text.splitlines()[1:]).strip()
    return PairwiseResult(winner=winner, rationale=rationale)


def panel_3(
    chat_fns: Sequence[ChatFn],
    *,
    prompt: str,
) -> tuple[str, ...]:
    """同じ prompt を 3 体の判定器に投げ、3 件の判定結果を集める.

    多数決はユーザー側で行う. 雛形では n=3 固定とし、シーケンス長が 3 未満なら
    ValueError. 4 以上のときは先頭 3 件のみ使う.
    """
    if len(chat_fns) < 3:
        raise ValueError(
            f"panel_3 requires at least 3 chat_fns, got {len(chat_fns)}"
        )
    return tuple(chat_fns[i](prompt) for i in range(3))


def human_calibration_score(
    judge_outputs: Sequence[str],
    human_outputs: Sequence[str],
) -> float:
    """LLM judge 出力と人手出力の一致率を返す.

    判定器の妥当性確認用. 雛形では strip 後の文字列完全一致で測る.
    Phase 6 以降で編集距離・カテゴリ別精度等に拡張する.
    """
    if not human_outputs:
        return 0.0
    if len(judge_outputs) != len(human_outputs):
        raise ValueError(
            f"length mismatch: judge={len(judge_outputs)}, human={len(human_outputs)}"
        )
    n_match = sum(
        1 for j, h in zip(judge_outputs, human_outputs) if j.strip() == h.strip()
    )
    return n_match / len(human_outputs)
