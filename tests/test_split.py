"""層化分割ユーティリティのテスト."""

from __future__ import annotations

import pytest

from tsumiki.eval.split import (
    SplitConfig,
    primary_pattern_key,
    stratified_split,
)

SEV = {
    "A": "high",
    "B": "medium",
    "C": "low",
}


def test_primary_pattern_key_picks_highest_severity() -> None:
    assert primary_pattern_key(frozenset({"A", "B", "C"}), SEV) == "A"
    assert primary_pattern_key(frozenset({"B", "C"}), SEV) == "B"
    assert primary_pattern_key(frozenset(), SEV) == "__none__"


def test_primary_pattern_key_stable_on_tie() -> None:
    # A2 と A1 を同 severity high にし、辞書順で決定論的に決まることを確認
    sev = {"A1": "high", "A2": "high"}
    assert primary_pattern_key(frozenset({"A2", "A1"}), sev) == "A1"


def test_split_ratios_close_to_target() -> None:
    samples = [(i, frozenset({"A"}) if i % 3 == 0 else frozenset()) for i in range(120)]
    cfg = SplitConfig(seed=42)
    train, val, test = stratified_split(samples, lambda s: s[1], SEV, cfg)
    assert len(train) + len(val) + len(test) == 120
    assert abs(len(train) / 120 - 0.7) < 0.05
    assert abs(len(val) / 120 - 0.15) < 0.05


def test_split_is_deterministic() -> None:
    samples = [(i, frozenset({"A"}) if i % 2 else frozenset({"B"})) for i in range(50)]
    cfg = SplitConfig(seed=7)
    r1 = stratified_split(samples, lambda s: s[1], SEV, cfg)
    r2 = stratified_split(samples, lambda s: s[1], SEV, cfg)
    assert r1 == r2


def test_split_different_seeds_differ() -> None:
    samples = [(i, frozenset({"A"})) for i in range(50)]
    r1 = stratified_split(samples, lambda s: s[1], SEV, SplitConfig(seed=1))
    r2 = stratified_split(samples, lambda s: s[1], SEV, SplitConfig(seed=2))
    assert r1 != r2


def test_split_preserves_strata_proportions() -> None:
    # A 群が 60, none 群が 40 → train 70%, val 15%, test 15% で割ったとき
    # 各 split で A 群比率がほぼ 60% に近いはず
    samples = (
        [(i, frozenset({"A"})) for i in range(60)]
        + [(i + 60, frozenset()) for i in range(40)]
    )
    cfg = SplitConfig(seed=42)
    train, val, test = stratified_split(samples, lambda s: s[1], SEV, cfg)
    for split in (train, val, test):
        a_count = sum(1 for _, ng in split if "A" in ng)
        ratio = a_count / max(len(split), 1)
        assert abs(ratio - 0.6) < 0.1  # 10% 以内


def test_invalid_split_config_raises() -> None:
    with pytest.raises(ValueError):
        SplitConfig(seed=1, train_ratio=0.0)
    with pytest.raises(ValueError):
        SplitConfig(seed=1, train_ratio=0.7, val_ratio=0.4)  # > 1 で test 残らず
