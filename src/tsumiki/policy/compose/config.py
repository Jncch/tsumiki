"""ComposeConfig / ComposeResult: tsumiki.policy.compose の入出力 dataclass.

Phase 7e-4 (2026-06-19) で追加. 設計書 `phase7e_design.md` §4.2.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tsumiki.goal.specs import EvaluatorSpec, TaskSpec
from tsumiki.knowledge.schemas.ng_patterns import NGPatternBook
from tsumiki.llm.client import LLMSettings

ChatFn = Callable[[str], str]
JsonChatFn = Callable[[list[dict[str, str]]], dict[str, Any]]
BenchmarkFn = Callable[[dict[str, str]], float]


@dataclass(frozen=True)
class ComposeConfig:
    """`run_compose` の入力. 評価器・知識・LLM 設定を 1 まとめにする.

    Fields:
        task_spec: 自然言語目的の構造化表現 (Phase 5c TaskSpec).
        evaluator_spec: 承認済み EvaluatorSpec (`approved_by != ""` が前提).
        knowledge: ドメイン知識 (NDA / ISO27001 等の NGPatternBook).
        llm_settings: LLM プロバイダ設定 (ollama / OpenAI / Azure).
        chat_fn: 通常 chat 用 (recombination).
        json_chat_fn: JSON 応答用 (evolution).
        benchmark_fn: Agent 構成 -> performance を返す評価器 wrapper.
        max_search_depth: AgentSquare 探索ループ回数.
        seed: 乱数シード (CLAUDE.md §4 で固定要求).
    """

    task_spec: TaskSpec
    evaluator_spec: EvaluatorSpec
    knowledge: NGPatternBook
    llm_settings: LLMSettings
    chat_fn: ChatFn
    json_chat_fn: JsonChatFn
    benchmark_fn: BenchmarkFn
    max_search_depth: int = 3
    seed: int = 42


@dataclass(frozen=True)
class ComposeResult:
    """`run_compose` の出力. AgentSquare 探索の結果 + 履歴.

    Fields:
        selected_modules: 探索で得た最良の Agent 構成 (planning/reasoning/tooluse/memory).
        search_score: 最良スコア (benchmark_fn の最終値).
        search_history: 探索中の tested_cases 全件 (MLflow ロギング用).
        test_counts: 各 iteration の探索回数.
    """

    selected_modules: dict[str, str]
    search_score: float
    search_history: list[dict[str, Any]] = field(default_factory=list)
    test_counts: dict[str, Any] = field(default_factory=dict)
