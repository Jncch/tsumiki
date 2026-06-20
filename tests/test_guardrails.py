"""LLM judge ガードレールのテスト. Phase 5c-5."""

from __future__ import annotations

import pytest

from tsumiki.eval.core import (
    PairwiseResult,
    human_calibration_score,
    pairwise,
    panel_3,
)


def test_pairwise_winner_a() -> None:
    result = pairwise(
        lambda _: "A\nA の方が明確",
        candidate_a="aaa",
        candidate_b="bbb",
        criterion="明確さ",
    )
    assert isinstance(result, PairwiseResult)
    assert result.winner == "A"
    assert "明確" in result.rationale


def test_pairwise_winner_b() -> None:
    result = pairwise(
        lambda _: "B\nB が優れる",
        candidate_a="a",
        candidate_b="b",
        criterion="x",
    )
    assert result.winner == "B"


def test_pairwise_tie_on_unknown_first_line() -> None:
    result = pairwise(
        lambda _: "UNCLEAR\nどちらとも言えない",
        candidate_a="a",
        candidate_b="b",
        criterion="x",
    )
    assert result.winner == "TIE"


def test_pairwise_tie_explicit() -> None:
    result = pairwise(
        lambda _: "TIE",
        candidate_a="a",
        candidate_b="b",
        criterion="x",
    )
    assert result.winner == "TIE"


def test_panel_3_basic() -> None:
    fns = (
        lambda p: f"j1:{p}",
        lambda p: f"j2:{p}",
        lambda p: f"j3:{p}",
    )
    out = panel_3(fns, prompt="hello")
    assert out == ("j1:hello", "j2:hello", "j3:hello")


def test_panel_3_requires_3_fns() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        panel_3((lambda p: p, lambda p: p), prompt="x")


def test_human_calibration_score_full_match() -> None:
    assert human_calibration_score(("a", "b"), ("a", "b")) == 1.0


def test_human_calibration_score_partial() -> None:
    score = human_calibration_score(("yes", "yes", "no"), ("yes", "no", "no"))
    assert abs(score - 2 / 3) < 1e-9


def test_human_calibration_score_strips_whitespace() -> None:
    assert human_calibration_score((" yes ", "no"), ("yes", " no")) == 1.0


def test_human_calibration_score_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length mismatch"):
        human_calibration_score(("a",), ("a", "b"))


def test_human_calibration_score_empty_human() -> None:
    assert human_calibration_score((), ()) == 0.0
