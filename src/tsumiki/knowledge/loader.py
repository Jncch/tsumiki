"""NG パターン辞書のローダー."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Literal

import yaml

Severity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class TopicVocab:
    """条文の主題語彙. ng_patterns v0.3.0 以降で applicable_topics の参照先となる."""

    id: str
    name: str


@dataclass(frozen=True)
class NGPattern:
    id: str
    name: str
    description: str
    severity: Severity
    excerpt_examples: tuple[str, ...] = field(default_factory=tuple)
    references: tuple[str, ...] = field(default_factory=tuple)
    # v0.3.0 以降: 各パターンが判定対象とする条文の主題（TopicVocab.id 集合）。
    # 空タプルなら「全条文を判定対象にする」（v0.2.0 以前の互換挙動）。
    applicable_topics: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class NGPatternBook:
    version: str
    contract_type: str
    last_updated: str
    maintainer: str
    patterns: tuple[NGPattern, ...]
    # v0.3.0 以降: 主題語彙のコントロールド・ボキャブラリ。空タプルなら主題判定なし。
    topics: tuple[TopicVocab, ...] = field(default_factory=tuple)

    def ids(self) -> tuple[str, ...]:
        return tuple(p.id for p in self.patterns)

    def by_id(self, pattern_id: str) -> NGPattern:
        for p in self.patterns:
            if p.id == pattern_id:
                return p
        raise KeyError(pattern_id)

    def topic_ids(self) -> tuple[str, ...]:
        return tuple(t.id for t in self.topics)


def _coerce_severity(raw: object) -> Severity:
    if raw in ("low", "medium", "high"):
        return raw  # type: ignore[return-value]
    raise ValueError(f"invalid severity: {raw!r}")


def _parse_topics(raw: object) -> tuple[TopicVocab, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError("topics must be a list")
    out: list[TopicVocab] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError(f"topic entry must be a mapping, got {type(entry).__name__}")
        tid = str(entry["id"])
        if tid in seen:
            raise ValueError(f"duplicate topic id: {tid}")
        seen.add(tid)
        out.append(TopicVocab(id=tid, name=str(entry["name"])))
    return tuple(out)


def _parse(doc: dict[str, object]) -> NGPatternBook:
    topics = _parse_topics(doc.get("topics"))
    topic_ids = {t.id for t in topics}

    patterns_raw = doc.get("patterns")
    if not isinstance(patterns_raw, list):
        raise ValueError("patterns must be a list")
    patterns: list[NGPattern] = []
    seen_ids: set[str] = set()
    for entry in patterns_raw:
        if not isinstance(entry, dict):
            raise ValueError(f"pattern entry must be a mapping, got {type(entry).__name__}")
        pid = str(entry["id"])
        if pid in seen_ids:
            raise ValueError(f"duplicate pattern id: {pid}")
        seen_ids.add(pid)

        applicable_topics_raw = entry.get("applicable_topics", [])
        if not isinstance(applicable_topics_raw, list):
            raise ValueError(
                f"applicable_topics must be a list for pattern {pid}"
            )
        applicable_topics = tuple(str(x) for x in applicable_topics_raw)
        # topics が定義されている場合は applicable_topics が語彙に含まれていることを検証
        if topic_ids:
            unknown = set(applicable_topics) - topic_ids
            if unknown:
                raise ValueError(
                    f"pattern {pid} references unknown topics: {sorted(unknown)}"
                )

        patterns.append(
            NGPattern(
                id=pid,
                name=str(entry["name"]),
                description=str(entry["description"]).strip(),
                severity=_coerce_severity(entry.get("severity", "medium")),
                excerpt_examples=tuple(str(x) for x in entry.get("excerpt_examples", [])),
                references=tuple(str(x) for x in entry.get("references", [])),
                applicable_topics=applicable_topics,
            )
        )
    return NGPatternBook(
        version=str(doc["version"]),
        contract_type=str(doc["contract_type"]),
        last_updated=str(doc["last_updated"]),
        maintainer=str(doc.get("maintainer", "")),
        patterns=tuple(patterns),
        topics=topics,
    )


def load_ng_patterns(contract_type: str = "nda") -> NGPatternBook:
    """同梱の知識資産から NG パターン辞書をロードする.

    contract_type に対応する `src/tsumiki/knowledge/<contract_type>/ng_patterns.yaml` を読む。
    """
    resource = files("tsumiki.knowledge").joinpath(contract_type, "ng_patterns.yaml")
    text = resource.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise ValueError(f"yaml root must be a mapping, got {type(doc).__name__}")
    return _parse(doc)


def load_ng_patterns_from_path(path: Path) -> NGPatternBook:
    """任意パスから NG パターン辞書をロードする（実験用）."""
    text = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise ValueError(f"yaml root must be a mapping, got {type(doc).__name__}")
    return _parse(doc)
