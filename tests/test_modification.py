"""Phase 2 修正評価器のテスト."""

from __future__ import annotations

from tsumiki.eval.modification import (
    build_outcome,
    compute_modification_report,
)


def _o(sid: str, truth: list[str], detected: list[str]):
    return build_outcome(
        sample_id=sid,
        original_text="orig",
        truth_pattern_ids=frozenset(truth),
        modified_text="mod",
        detected_after=frozenset(detected),
    )


def test_target_removed_when_all_truth_disappears() -> None:
    o = _o("s1", ["A", "B"], ["C"])
    assert o.target_removed is True
    assert o.new_ng_introduced is True  # C は truth に無い


def test_target_not_removed_when_any_truth_remains() -> None:
    o = _o("s2", ["A"], ["A", "B"])
    assert o.target_removed is False
    assert o.new_ng_introduced is True  # B は新規


def test_no_negative_transfer_when_detected_subset_of_truth() -> None:
    o = _o("s3", ["A", "B"], ["A"])
    assert o.target_removed is False
    assert o.new_ng_introduced is False


def test_perfect_modification() -> None:
    o = _o("s4", ["A"], [])
    assert o.target_removed is True
    assert o.new_ng_introduced is False


def test_truth_empty_target_not_counted() -> None:
    """truth が空のサンプルは target_removed=False（修正対象なし）."""
    o = _o("s5", [], [])
    assert o.target_removed is False
    assert o.new_ng_introduced is False


def test_report_aggregates_success_and_transfer() -> None:
    outs = [
        _o("a", ["A"], []),
        _o("b", ["A"], ["A"]),
        _o("c", ["B"], ["B", "C"]),
        _o("d", ["B"], []),
    ]
    rep = compute_modification_report(outs)
    assert rep.n_samples == 4
    assert rep.n_target_removed == 2  # a, d
    assert rep.modification_success_rate == 0.5
    assert rep.n_new_ng_introduced == 1  # c
    assert rep.negative_transfer_rate == 0.25
    # per-pattern: A は a/2=0.5、B は d/2=0.5
    assert rep.per_pattern_success["A"] == 0.5
    assert rep.per_pattern_success["B"] == 0.5
    assert rep.per_pattern_support == {"A": 2, "B": 2}


def test_report_empty() -> None:
    rep = compute_modification_report([])
    assert rep.n_samples == 0
    assert rep.modification_success_rate == 0.0
    assert rep.per_pattern_success == {}
