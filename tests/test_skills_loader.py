"""Agent Skills 標準ローダーのテスト. Phase 5b 情報等価性ゲート."""

from __future__ import annotations

from pathlib import Path

import pytest

from tsumiki.knowledge import load_ng_patterns
from tsumiki.knowledge.loader import load_ng_patterns_auto
from tsumiki.knowledge.skills_loader import (
    build_description,
    load_skill,
    load_skills_dir,
    parse_skill_markdown,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NDA_SKILLS_DIR = (
    PROJECT_ROOT / "src" / "tsumiki" / "knowledge" / "skills" / "nda" / "ng_patterns"
)


@pytest.fixture(scope="module")
def yaml_book():
    return load_ng_patterns("nda")


@pytest.fixture(scope="module")
def skills_book():
    return load_skills_dir(NDA_SKILLS_DIR)


def test_skills_dir_exists() -> None:
    assert NDA_SKILLS_DIR.is_dir(), (
        f"build_nda_skills.py 未実行か出力先がずれている: {NDA_SKILLS_DIR}"
    )
    assert (NDA_SKILLS_DIR / "_index.yaml").is_file()


def test_pattern_count_matches(yaml_book, skills_book) -> None:
    assert len(yaml_book.patterns) == len(skills_book.patterns)


def test_pattern_ids_match(yaml_book, skills_book) -> None:
    assert set(yaml_book.ids()) == set(skills_book.ids())


def test_pattern_equivalence_per_id(yaml_book, skills_book) -> None:
    skills_by_id = {p.id: p for p in skills_book.patterns}
    for yp in yaml_book.patterns:
        sp = skills_by_id[yp.id]
        assert sp.name == yp.name, f"{yp.id} name mismatch"
        assert sp.severity == yp.severity, f"{yp.id} severity mismatch"
        assert sp.applicable_topics == yp.applicable_topics, (
            f"{yp.id} applicable_topics mismatch"
        )
        assert sp.references == yp.references, f"{yp.id} references mismatch"
        assert sp.excerpt_examples == yp.excerpt_examples, (
            f"{yp.id} excerpt_examples mismatch"
        )
        # description は strip + section 順序統一で比較
        assert sp.description == yp.description, (
            f"{yp.id} description mismatch\n--- yaml ---\n{yp.description}\n"
            f"--- skills ---\n{sp.description}"
        )


def test_topics_match(yaml_book, skills_book) -> None:
    assert yaml_book.topics == skills_book.topics


def test_metadata_match(yaml_book, skills_book) -> None:
    assert skills_book.contract_type == yaml_book.contract_type
    assert skills_book.version == yaml_book.version
    assert skills_book.last_updated == yaml_book.last_updated
    assert skills_book.maintainer == yaml_book.maintainer


def test_load_ng_patterns_auto_directory(yaml_book) -> None:
    book = load_ng_patterns_auto(NDA_SKILLS_DIR)
    assert set(book.ids()) == set(yaml_book.ids())


def test_load_ng_patterns_auto_yaml() -> None:
    book = load_ng_patterns_auto(
        PROJECT_ROOT / "src" / "tsumiki" / "knowledge" / "nda" / "ng_patterns.yaml"
    )
    assert len(book.patterns) >= 5


def test_parse_skill_markdown_basic() -> None:
    text = (
        "---\n"
        "id: foo\n"
        "name: 名前\n"
        "domain: test\n"
        "schema_version: 1\n"
        "---\n"
        "\n"
        "# 名前\n"
        "\n"
        "## 対象条項\n"
        "\n"
        "対象本文\n"
        "\n"
        "## 検出すべき\n"
        "\n"
        "検出本文\n"
        "\n"
        "## 紛らわしい\n"
        "\n"
        "紛らわしい本文\n"
        "\n"
        "## 例\n"
        "\n"
        "- 例 1\n"
        "- 例 2\n"
    )
    frontmatter, sections, examples = parse_skill_markdown(text)
    assert frontmatter["id"] == "foo"
    assert sections["対象条項"] == "対象本文"
    assert sections["検出すべき"] == "検出本文"
    assert sections["紛らわしい"] == "紛らわしい本文"
    assert examples == ["例 1", "例 2"]


def test_build_description_order() -> None:
    """description は 検出すべき → 紛らわしい → 対象条項 の順で組み立てられる."""
    desc = build_description(
        {
            "対象条項": "T",
            "検出すべき": "D",
            "紛らわしい": "C",
        }
    )
    assert desc == "検出すべき: D\n紛らわしい: C\n対象条項: T"


def test_load_skill_individual() -> None:
    path = NDA_SKILLS_DIR / "nda_scope_overbroad.md"
    pattern, frontmatter = load_skill(path)
    assert pattern.id == "nda_scope_overbroad"
    assert pattern.severity == "high"
    assert "definition" in pattern.applicable_topics
    assert frontmatter["domain"] == "nda"
