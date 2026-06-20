"""Phase 6 generator パスの単体テスト.

ISO27001 用 TaskSpec を組み立て、generator を 1 回呼んで EvaluatorSpec が生成され
verifier が通るかを単独で確認する. 試走 (約 90 分) を流す前に低コストで動作確認する.

設計: docs/experiments/phase6_design.md §4.3, §7

実行例:
    LLM_BASE_URL=http://localhost:11434/v1 \\
    LLM_API_KEY=ollama \\
    LLM_MODEL=qwen25-14b-ctx8k \\
    uv run python experiments/test_phase6_generator.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from tsumiki.data.synthesis import make_openai_chat_fn
from tsumiki.goal import (
    InputRole,
    KnowledgeSource,
    OutputSchema,
    TaskSpec,
)
from tsumiki.goal.generator import generate_evaluator
from tsumiki.goal.render import evaluator_spec_summary
from tsumiki.goal.verifier import verify
from tsumiki.llm import LLMSettings, build_client
from tsumiki.runner.e2e import _to_text_chat_fn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def make_iso27001_task_spec() -> TaskSpec:
    return TaskSpec(
        task_class="detect_and_modify",
        domain="iso27001",
        input_roles=(
            InputRole(
                name="target_document",
                formats=("pdf", "docx", "md", "txt"),
                role="target",
                description="チェック対象の運用文書または統制記述",
            ),
        ),
        knowledge=KnowledgeSource(
            source_type="existing",
            catalog_path="knowledge/skills/iso27001/audit_findings/",
        ),
        outputs=(
            OutputSchema(
                name="findings",
                schema_id="audit_findings_v1",
                description="検出された統制不備リスト",
            ),
            OutputSchema(
                name="modified_document",
                schema_id="modified_text_v1",
                description="是正後の統制記述文",
            ),
        ),
        evaluator_hints=(
            "target_pattern が修正後に残らない率を測りたい",
            "target 以外の不備が新規発生する率（negative_transfer）も測る",
        ),
        raw_goal="ISO27001 の運用文書をチェックして統制不備を是正したい",
    )


def main() -> int:
    base_url = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
    api_key = os.environ.get("LLM_API_KEY", "ollama")
    model = os.environ.get("LLM_MODEL", "qwen25-14b-ctx8k")
    settings = LLMSettings(
        provider="openai_compatible",
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=0.0,
    )
    client = build_client(settings)
    rich_chat_fn = make_openai_chat_fn(
        client, model, temperature=0.0, seed=42, num_ctx=8192
    )
    chat_fn = _to_text_chat_fn(rich_chat_fn)

    task = make_iso27001_task_spec()
    print(f"[test] generating evaluator for domain={task.domain} task_class={task.task_class}")
    try:
        spec = generate_evaluator(
            task,
            chat_fn,
            generated_at="2026-06-19",
            approved_by="phase6_test",
        )
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] generator raised {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print("\n========== Generated EvaluatorSpec ==========")
    print(evaluator_spec_summary(spec))
    print("=============================================")

    print("\n[test] running verifier...")
    result = verify(spec)
    if result.error is not None:
        print(f"[FAIL] verifier error: {result.error}", file=sys.stderr)
        return 1
    if not result.passed:
        print("[FAIL] verifier failures:")
        for f in result.failures:
            print(f"  - {f}")
        return 1
    print(f"[OK] generator + verifier passed. type={spec.type} test_cases={len(spec.test_cases)}")
    print("    本番試走に進める. 評価器は保存していない.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
