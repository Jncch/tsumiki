"""流用蓄積からの評価器検索.

Q4=B により検索粒度は `domain` + `task_class` + 入出力スキーマの一致.
embedding 類似度マッチは Phase 7 以降の最適化として後付け.

設計: docs/experiments/phase5c_design.md §2 `goal/lookup.py`
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tsumiki.goal.specs import EvaluatorSpec, TaskSpec
from tsumiki.goal.store import META_YAML, load


@dataclass(frozen=True)
class LookupCandidate:
    """流用候補. exact_match なら全一致, partial_match なら domain+task_class のみ一致."""

    spec: EvaluatorSpec
    exact_match: bool


def _iter_evaluator_dirs(root: Path) -> list[Path]:
    """root 直下の <domain>/<task_class>/<id>/ ディレクトリ群を列挙する."""
    if not root.is_dir():
        return []
    found: list[Path] = []
    for domain_dir in sorted(root.iterdir()):
        if not domain_dir.is_dir():
            continue
        for task_class_dir in sorted(domain_dir.iterdir()):
            if not task_class_dir.is_dir():
                continue
            for eval_dir in sorted(task_class_dir.iterdir()):
                if eval_dir.is_dir() and (eval_dir / META_YAML).is_file():
                    found.append(eval_dir)
    return found


def search(
    root: Path,
    task_spec: TaskSpec,
    *,
    include_partial: bool = False,
) -> list[LookupCandidate]:
    """流用蓄積から候補を検索する.

    - exact_match=True: domain + task_class + 入出力シグネチャが完全一致
    - exact_match=False かつ include_partial=True: domain + task_class のみ一致

    Returns: exact_match 優先で並べた候補リスト.
    """
    target_sig = task_spec.io_signature()
    candidates: list[LookupCandidate] = []
    for eval_dir in _iter_evaluator_dirs(root):
        try:
            spec = load(eval_dir)
        except Exception:  # noqa: BLE001
            # 壊れた評価器ディレクトリは無視
            continue
        if spec.domain != task_spec.domain:
            continue
        if spec.task_class != task_spec.task_class:
            continue
        if spec.input_signature == target_sig:
            candidates.append(LookupCandidate(spec=spec, exact_match=True))
        elif include_partial:
            candidates.append(LookupCandidate(spec=spec, exact_match=False))
    # exact_match を先頭に
    candidates.sort(key=lambda c: (not c.exact_match, c.spec.id))
    return candidates
