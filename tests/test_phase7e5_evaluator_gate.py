"""Phase 7e-5: 評価器 gate 整理.

設計書 `phase7e_design.md` §6.2 (Phase 7e-5 ゲート).
CLAUDE.md §9 (評価器が無い状態で自動探索を回さない) を体現するため,
`EvaluatorSpec.is_approved()` メソッド + `_assert_evaluator_gate_passed` の動作を
代表的なパス (lookup hit / generator パス) で確認する.

7e-4 では `_assert_evaluator_gate_passed` の単純な承認済/未承認 test だけだった.
7e-5 では `EvaluatorSpec.is_approved()` メソッドの追加と, 評価器が生まれる経路
(lookup / store / generator) で `approved_by` が正しく設定されることを確認する.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tsumiki.goal.specs import (
    EvaluatorSpec,
    KnowledgeSource,
    OutputSchema,
    TaskSpec,
)
from tsumiki.policy.compose import _assert_evaluator_gate_passed


def _eval(approved_by: str = "auto", **overrides) -> EvaluatorSpec:
    base = {
        "id": "dummy_eval_v1",
        "domain": "nda",
        "task_class": "detect",
        "type": "deterministic",
        "input_signature": ((), ()),
        "output_metrics": ("findings_recall",),
        "implementation": "def evaluate(outcomes): return {}",
        "test_cases": (),
        "guardrails": (),
        "sources": (),
        "generated_at": "2026-06-19",
        "approved_by": approved_by,
    }
    base.update(overrides)
    return EvaluatorSpec(**base)


# === EvaluatorSpec.is_approved() の単体動作 ===


@pytest.mark.parametrize(
    ("approved_by", "expected"),
    [
        ("auto", True),
        ("user", True),
        ("jncch", True),
        ("", False),
    ],
)
def test_is_approved_judges_by_approved_by(approved_by: str, expected: bool) -> None:
    spec = _eval(approved_by=approved_by)
    assert spec.is_approved() is expected


def test_is_approved_uses_truthiness() -> None:
    """空白だけは "approved" として扱う (truthiness ベース判定)."""
    spec = _eval(approved_by=" ")
    assert spec.is_approved() is True


# === compose の gate が is_approved() 経由で判定する ===


def test_assert_gate_uses_is_approved() -> None:
    """`_assert_evaluator_gate_passed` が is_approved() 経由で動作することを確認."""
    spec = _eval(approved_by="")
    # is_approved() が False のとき gate は RuntimeError
    assert spec.is_approved() is False
    with pytest.raises(RuntimeError):
        _assert_evaluator_gate_passed(spec)


# === lookup hit 経路: store の save/load ラウンドトリップで approved_by が保持される ===


def _task_spec() -> TaskSpec:
    return TaskSpec(
        task_class="detect",
        domain="nda",
        input_roles=(),
        knowledge=KnowledgeSource(source_type="existing", catalog_path="dummy"),
        outputs=(OutputSchema(name="findings", schema_id="ng_findings_v1"),),
        raw_goal="test",
    )


def test_store_roundtrip_preserves_approved_by(tmp_path: Path) -> None:
    """store.save → store.load で approved_by が保持されることを確認.

    Phase 5c 以降の lookup パスは `store.save` で書いた評価器を `lookup.search` →
    `store.load` で読む. ここで `approved_by` が落ちると gate を素通りされる.
    """
    from tsumiki.goal import store

    spec = _eval(approved_by="auto")
    eval_dir = store.save(tmp_path, spec)

    loaded = store.load(eval_dir)
    assert loaded.approved_by == "auto"
    assert loaded.is_approved() is True
    # gate を通過する
    _assert_evaluator_gate_passed(loaded)


def test_store_load_treats_missing_approved_by_as_empty(tmp_path: Path) -> None:
    """meta.yaml に approved_by フィールドが無い場合は空文字扱い.

    `store.load` の `meta.get("approved_by", "")` を確認. gate は raise.
    """
    from tsumiki.goal import store

    spec = _eval(approved_by="")
    eval_dir = store.save(tmp_path, spec)

    loaded = store.load(eval_dir)
    assert loaded.approved_by == ""
    assert loaded.is_approved() is False
    with pytest.raises(RuntimeError):
        _assert_evaluator_gate_passed(loaded)


# === generator 経路: generate_evaluator が approved_by="auto" デフォルトを設定する ===


def test_generator_default_approved_by_is_auto() -> None:
    """`generate_evaluator(...)` のデフォルト `approved_by="auto"` が is_approved()=True になる.

    LLM 呼び出しは mock chat_fn で代替し generator の return value だけ確認する.
    """
    from tsumiki.goal.generator import generate_evaluator

    def mock_chat(_prompt: str) -> str:
        # generator が期待する JSON object の最小スキーマ.
        # task_spec の domain / task_class / input_signature は generator 側が上書きする.
        return (
            '{"id": "gen_eval_v1", "type": "deterministic", '
            '"output_metrics": ["m"], "implementation": '
            '"def evaluate(outcomes: list[dict]) -> dict: return {}", '
            '"test_cases": [], "guardrails": [], "sources": [], "notes": ""}'
        )

    spec = generate_evaluator(
        task_spec=_task_spec(),
        chat_fn=mock_chat,
        generated_at="2026-06-19",
    )
    assert spec.approved_by == "auto"
    assert spec.is_approved() is True
    _assert_evaluator_gate_passed(spec)


def test_generator_explicit_empty_approved_by_fails_gate() -> None:
    """generator が `approved_by=""` (人手承認待ち) で出した spec は gate で raise."""
    from tsumiki.goal.generator import generate_evaluator

    def mock_chat(_prompt: str) -> str:
        return (
            '{"id": "gen_eval_v1", "type": "deterministic", '
            '"output_metrics": ["m"], "implementation": '
            '"def evaluate(outcomes: list[dict]) -> dict: return {}", '
            '"test_cases": [], "guardrails": [], "sources": [], "notes": ""}'
        )

    spec = generate_evaluator(
        task_spec=_task_spec(),
        chat_fn=mock_chat,
        generated_at="2026-06-19",
        approved_by="",
    )
    assert spec.is_approved() is False
    with pytest.raises(RuntimeError):
        _assert_evaluator_gate_passed(spec)


# === 既存 generated 評価器 (eval/generated/ 配下) の approved_by 確認 ===


def test_existing_generated_evaluators_have_approved_by() -> None:
    """`src/tsumiki/eval/generated/` 配下の seed/承認済評価器は全て approved_by が設定済.

    7e-6 試走で `examples/{nda,iso27001}/run.sh --use-compose` が gate を通過するための
    前提を確認.
    """
    from tsumiki.goal import store

    root = Path(__file__).resolve().parent.parent / "src" / "tsumiki" / "eval" / "generated"
    if not root.exists():
        pytest.skip(f"{root} が存在しない (試走前は省略可)")

    # meta.yaml を持つディレクトリを再帰検索
    eval_dirs = [p.parent for p in root.rglob("meta.yaml")]
    assert eval_dirs, "eval/generated/ 配下に meta.yaml が 1 つも無い"

    for eval_dir in eval_dirs:
        try:
            spec = store.load(eval_dir)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"{eval_dir.name} を load 失敗: {e}")
        assert spec.is_approved(), (
            f"{eval_dir.relative_to(root)} の approved_by が空. "
            f"compose gate を素通りされない設計のため設定必須."
        )
