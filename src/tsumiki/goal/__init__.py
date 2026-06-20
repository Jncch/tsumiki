"""Goal-driven setup for tsumiki.

Phase 5c で導入。自然言語の目的を構造化スキーマに変換し、評価器を生成・承認・蓄積する。

設計: docs/experiments/phase5c_design.md
"""

from tsumiki.goal.specs import (
    EvaluatorSpec,
    InputRole,
    KnowledgeSource,
    OutputSchema,
    TaskSpec,
    TestCase,
)

__all__ = [
    "EvaluatorSpec",
    "InputRole",
    "KnowledgeSource",
    "OutputSchema",
    "TaskSpec",
    "TestCase",
]
