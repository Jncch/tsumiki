"""層化 train/val/test 分割.

CLAUDE.md §4 の「test 分割は層化して固定し、一度確定したら変更しない」を担保する.

多ラベル分類のため厳密な層化（iterative stratification）は重いので、
ここでは「最重大の NG パターン」を strata キーにする実用的な代替を採る:
- NG なしサンプルは "__none__" 群
- 複数 NG を持つサンプルは severity (high>medium>low) で最重大のものに割り当て
- 同 severity ならば pattern id の辞書順で安定的に決める
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True)
class SplitConfig:
    seed: int
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    # test_ratio は残差 (1 - train - val)

    def __post_init__(self) -> None:
        if not (0 < self.train_ratio < 1):
            raise ValueError("train_ratio must be in (0,1)")
        if not (0 <= self.val_ratio < 1):
            raise ValueError("val_ratio must be in [0,1)")
        if self.train_ratio + self.val_ratio >= 1.0:
            raise ValueError("train + val must be < 1.0 (test には > 0 を残す)")


def primary_pattern_key(
    ng_pattern_ids: frozenset[str],
    severity_by_id: dict[str, str],
) -> str:
    """最重大の NG パターン id を返す. 該当なしなら "__none__"."""
    if not ng_pattern_ids:
        return "__none__"
    ranked = sorted(
        ng_pattern_ids,
        key=lambda i: (-_SEVERITY_RANK.get(severity_by_id.get(i, "medium"), 2), i),
    )
    return ranked[0]


def stratified_split[T](
    samples: Sequence[T],
    label_fn: Callable[[T], frozenset[str]],
    severity_by_id: dict[str, str],
    config: SplitConfig,
) -> tuple[list[T], list[T], list[T]]:
    """primary pattern を strata キーとした 3-way 分割.

    各 strata 内で seed 固定の shuffle → 比率で分ける.
    返り値は (train, val, test).
    """
    by_strata: dict[str, list[T]] = {}
    for s in samples:
        key = primary_pattern_key(label_fn(s), severity_by_id)
        by_strata.setdefault(key, []).append(s)

    rng = random.Random(config.seed)
    train: list[T] = []
    val: list[T] = []
    test: list[T] = []
    # strata key の辞書順に処理して決定論性を保つ
    for key in sorted(by_strata.keys()):
        items = list(by_strata[key])
        rng.shuffle(items)
        n = len(items)
        n_train = int(n * config.train_ratio)
        n_val = int(n * config.val_ratio)
        train.extend(items[:n_train])
        val.extend(items[n_train : n_train + n_val])
        test.extend(items[n_train + n_val :])
    return train, val, test
