"""Agent Skills 標準（Markdown スキル）の NG パターンローダー.

設計: docs/experiments/phase5b_design.md §1, §3

Markdown フロントマター + 本文 H2 セクションを読み、既存の `NGPatternBook` 等価な
dataclass を返す。これにより YAML 経由でも Markdown 経由でも同じ下流コードが動く。
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from tsumiki.knowledge.schemas.ng_patterns import (
    NGPattern,
    NGPatternBook,
    Topic,
    _coerce_severity,
    _parse_topics,
)

# Phase 5b 以前の旧名 alias. 既存テストが import している.
TopicVocab = Topic

# YAML フロントマター抽出
_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
# H2 セクション見出し
_H2_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

# description 再構築時のセクション順序。YAML 元の出現順に合わせる。
DESCRIPTION_SECTION_ORDER: tuple[str, ...] = ("検出すべき", "紛らわしい", "対象条項")
EXAMPLES_SECTION_NAME = "例"


def parse_skill_markdown(
    text: str,
) -> tuple[dict, dict[str, str], list[str]]:
    """Markdown スキルをフロントマター・本文セクション・例リストに分解する."""
    match = _FRONTMATTER_PATTERN.match(text)
    if match is None:
        raise ValueError("frontmatter (---) not found at top of skill markdown")
    frontmatter_yaml = match.group(1)
    body = match.group(2)
    frontmatter = yaml.safe_load(frontmatter_yaml) or {}
    if not isinstance(frontmatter, dict):
        raise ValueError("frontmatter must be a mapping")

    sections: dict[str, str] = {}
    examples: list[str] = []
    h2_matches = list(_H2_PATTERN.finditer(body))
    for i, m in enumerate(h2_matches):
        section_name = m.group(1).strip()
        start = m.end()
        end = h2_matches[i + 1].start() if i + 1 < len(h2_matches) else len(body)
        section_body = body[start:end].strip()
        if section_name == EXAMPLES_SECTION_NAME:
            for raw in section_body.splitlines():
                stripped = raw.strip()
                if stripped.startswith("- "):
                    examples.append(stripped[2:].strip())
                elif stripped.startswith("-"):
                    examples.append(stripped[1:].strip())
        else:
            sections[section_name] = section_body
    return frontmatter, sections, examples


def build_description(sections: dict[str, str]) -> str:
    """セクション辞書から description（YAML 元の文字列形式）を組み立てる."""
    parts: list[str] = []
    for name in DESCRIPTION_SECTION_ORDER:
        body = sections.get(name, "").strip()
        if body:
            parts.append(f"{name}: {body}")
    return "\n".join(parts)


def load_skill(path: Path) -> tuple[NGPattern, dict]:
    """1 スキル Markdown を読み、NGPattern とフロントマター辞書を返す."""
    text = path.read_text(encoding="utf-8")
    frontmatter, sections, examples = parse_skill_markdown(text)
    description = build_description(sections)
    applicable_topics = tuple(
        str(x) for x in (frontmatter.get("applicable_topics") or [])
    )
    pattern = NGPattern(
        id=str(frontmatter["id"]),
        name=str(frontmatter["name"]),
        description=description,
        severity=_coerce_severity(frontmatter.get("severity", "medium")),
        excerpt_examples=tuple(examples),
        references=tuple(str(x) for x in (frontmatter.get("references") or [])),
        applicable_topics=applicable_topics,
    )
    return pattern, frontmatter


def load_skills_dir(skills_dir: Path) -> NGPatternBook:
    """Agent Skills 形式のディレクトリ全体を NGPatternBook として読む.

    Required: <skills_dir>/_index.yaml
    Optional: <skills_dir>/topics.yaml
    """
    if not skills_dir.is_dir():
        raise NotADirectoryError(f"skills directory not found: {skills_dir}")
    index_path = skills_dir / "_index.yaml"
    if not index_path.is_file():
        raise FileNotFoundError(f"_index.yaml not found in {skills_dir}")
    index = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
    if not isinstance(index, dict):
        raise ValueError("_index.yaml root must be a mapping")
    domain = str(index.get("domain") or "unknown")
    source_version = str(index.get("source_version", ""))
    skills_entries = index.get("skills") or []

    topics_path = skills_dir / "topics.yaml"
    topics: tuple[TopicVocab, ...] = ()
    topics_last_updated = ""
    if topics_path.is_file():
        topics_doc = yaml.safe_load(topics_path.read_text(encoding="utf-8")) or {}
        if isinstance(topics_doc, dict):
            topics_last_updated = str(topics_doc.get("last_updated", ""))
            topics = _parse_topics(topics_doc.get("topics"))
    topic_ids = {t.id for t in topics}

    patterns: list[NGPattern] = []
    seen: set[str] = set()
    last_updated = topics_last_updated
    maintainer = ""
    for entry in skills_entries:
        if not isinstance(entry, dict):
            raise ValueError(
                f"skills entry must be a mapping, got {type(entry).__name__}"
            )
        skill_file = str(entry["file"])
        path = skills_dir / skill_file
        if not path.is_file():
            raise FileNotFoundError(f"skill file not found: {path}")
        pattern, frontmatter = load_skill(path)
        if pattern.id in seen:
            raise ValueError(f"duplicate pattern id: {pattern.id}")
        seen.add(pattern.id)
        if topic_ids:
            unknown = set(pattern.applicable_topics) - topic_ids
            if unknown:
                raise ValueError(
                    f"pattern {pattern.id} references unknown topics: {sorted(unknown)}"
                )
        patterns.append(pattern)
        if not last_updated:
            last_updated = str(frontmatter.get("last_updated", ""))
        if not maintainer:
            maintainer = str(frontmatter.get("maintainer", ""))

    return NGPatternBook(
        version=source_version,
        contract_type=domain,
        last_updated=last_updated,
        maintainer=maintainer,
        patterns=tuple(patterns),
        topics=topics,
    )
