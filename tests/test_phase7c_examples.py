"""Phase 7c: examples/{nda,iso27001}/ 同一フレーム動作 smoke test.

設計書 `phase7_design.md` §6.3 のゲートを確認する:
  1. 構造: README.md / goal.yaml / run.sh / knowledge / clean_clauses.jsonl が揃う
  2. 同一フレーム動作: 両 run.sh が同じ `runner/e2e.py` 系を呼ぶ
  3. baseline gate 表示: --baseline-paired-diff 引数を渡している
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"

DOMAINS = ("nda", "iso27001")


# === ゲート1: 構造が揃う ===


@pytest.mark.parametrize("domain", DOMAINS)
def test_example_layout_files_present(domain: str) -> None:
    base = EXAMPLES / domain
    assert (base / "README.md").is_file(), f"{domain}: README.md 欠落"
    assert (base / "goal.yaml").is_file(), f"{domain}: goal.yaml 欠落"
    assert (base / "run.sh").is_file(), f"{domain}: run.sh 欠落"


@pytest.mark.parametrize("domain", DOMAINS)
def test_example_knowledge_symlink_resolves(domain: str) -> None:
    """knowledge/ symlink が実体 (src/tsumiki/knowledge/skills/...) に到達する."""
    base = EXAMPLES / domain
    knowledge = base / "knowledge"
    assert knowledge.is_symlink(), f"{domain}: knowledge/ が symlink ではない"
    resolved = knowledge.resolve(strict=True)
    # tsumiki パッケージ内を指すこと
    rel = resolved.relative_to(REPO_ROOT)
    assert str(rel).startswith("src/tsumiki/knowledge/skills/"), (
        f"{domain}: knowledge symlink が tsumiki パッケージ外を指す: {rel}"
    )
    # スキル md ファイルが少なくとも 1 件存在
    md_files = list(resolved.glob("*.md"))
    assert len(md_files) >= 1, f"{domain}: knowledge/ 配下に .md スキルが無い"


@pytest.mark.parametrize("domain", DOMAINS)
def test_example_clean_clauses_symlink_targets_data_processed(domain: str) -> None:
    """clean_clauses.jsonl は data/processed/ への symlink (実体は環境依存で broken でも可)."""
    base = EXAMPLES / domain
    clauses = base / "clean_clauses.jsonl"
    assert clauses.is_symlink(), f"{domain}: clean_clauses.jsonl が symlink ではない"
    target = Path(str(clauses.readlink()))
    target_str = str(target)
    assert "data/processed" in target_str, (
        f"{domain}: clean_clauses.jsonl が data/processed/ を指さない: {target_str}"
    )


@pytest.mark.parametrize("domain", DOMAINS)
def test_goal_yaml_valid(domain: str) -> None:
    """goal.yaml が YAML として読め, domain / task_class / outputs が揃う."""
    base = EXAMPLES / domain
    with open(base / "goal.yaml", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    assert isinstance(doc, dict)
    assert doc["domain"] == domain
    assert doc["task_class"] == "detect_and_modify"
    assert "outputs" in doc
    assert any(o["name"] == "findings" for o in doc["outputs"])
    assert any(o["name"] == "modified_document" for o in doc["outputs"])


# === ゲート2: 同一フレーム動作 ===


_RUN_SH_RUNNER_PATTERN = re.compile(r"experiments/run_phase5c_dryrun\.py")


@pytest.mark.parametrize("domain", DOMAINS)
def test_run_sh_calls_same_runner(domain: str) -> None:
    """両 run.sh が同じ experiments/run_phase5c_dryrun.py を呼ぶ (同一フレーム動作)."""
    text = (EXAMPLES / domain / "run.sh").read_text(encoding="utf-8")
    assert _RUN_SH_RUNNER_PATTERN.search(text), (
        f"{domain}: run.sh が experiments/run_phase5c_dryrun.py を呼んでいない"
    )


def test_both_run_sh_share_runner() -> None:
    """NDA / ISO27001 の run.sh が呼ぶ runner が同一であることを直接比較."""
    nda = (EXAMPLES / "nda" / "run.sh").read_text(encoding="utf-8")
    iso = (EXAMPLES / "iso27001" / "run.sh").read_text(encoding="utf-8")
    nda_runners = set(_RUN_SH_RUNNER_PATTERN.findall(nda))
    iso_runners = set(_RUN_SH_RUNNER_PATTERN.findall(iso))
    assert nda_runners == iso_runners, (
        f"NDA / ISO27001 で runner が異なる: {nda_runners} vs {iso_runners}"
    )


# === ゲート3: baseline gate 表示の引数化 ===


_BASELINE_FLAG_PATTERN = re.compile(r"--baseline-paired-diff\s+(\S+)")


@pytest.mark.parametrize(
    "domain,expected",
    [
        ("nda", "0.261"),
        ("iso27001", "0.029"),
    ],
)
def test_run_sh_passes_baseline_flag(domain: str, expected: str) -> None:
    """run.sh が --baseline-paired-diff を渡している (Phase 7b 申し送り §7-6)."""
    text = (EXAMPLES / domain / "run.sh").read_text(encoding="utf-8")
    m = _BASELINE_FLAG_PATTERN.search(text)
    assert m is not None, f"{domain}: run.sh に --baseline-paired-diff が無い"
    assert m.group(1) == expected, (
        f"{domain}: --baseline-paired-diff {m.group(1)} が期待値 {expected} と不一致"
    )


# === ゲート4: skills_loader が schemas に依存 (Phase 7c-2) ===


def test_skills_loader_uses_schemas_not_loader_private() -> None:
    """skills_loader が `tsumiki.knowledge.schemas.ng_patterns` から import している
    (Phase 7c-2 で loader private 依存を解消)."""
    text = (
        REPO_ROOT / "src" / "tsumiki" / "knowledge" / "skills_loader.py"
    ).read_text(encoding="utf-8")
    assert "from tsumiki.knowledge.schemas.ng_patterns import" in text, (
        "skills_loader が schemas.ng_patterns から import していない"
    )
    # loader private 依存が残っていないこと
    assert "from tsumiki.knowledge.loader import (" not in text, (
        "skills_loader が loader からの private import を残している"
    )
