"""ドメイン横断の NG パターン共通 schema.

Phase 7b で `knowledge/loader.py` から dataclass と YAML パースを
移動して共通化した. NDA `ng_patterns.yaml` と ISO27001
`audit_findings.yaml` の両方がこの schema に乗ることを保証する.

historical note: dataclass attribute `contract_type` は v0.1 系の
YAML キー名をそのまま採用しており, 意味的には domain (ドメイン識別子)
を表す. ISO27001 の YAML でも `contract_type: iso27001` と書く.
正式な改名は破壊変更となるため Phase 9+ 以降に切り出す.
NGPatternBook.domain プロパティが Phase 7+ 以降の正式呼称.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

Severity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Topic:
    """主題語彙. ng_patterns v0.3.0 以降で applicable_topics の参照先."""

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
    # v0.3.0 以降: 各パターンが判定対象とする条文/統制条項の主題 (Topic.id 集合).
    # 空タプルなら「全条文を判定対象にする」(v0.2.0 以前の互換挙動).
    applicable_topics: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class NGPatternBook:
    version: str
    contract_type: str
    last_updated: str
    maintainer: str
    patterns: tuple[NGPattern, ...]
    # v0.3.0 以降: 主題語彙のコントロールド・ボキャブラリ. 空タプルなら主題判定なし.
    topics: tuple[Topic, ...] = field(default_factory=tuple)

    @property
    def domain(self) -> str:
        """Phase 7+ で導入した別名. 値は contract_type と同一."""
        return self.contract_type

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


def _parse_topics(raw: object) -> tuple[Topic, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError("topics must be a list")
    out: list[Topic] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError(f"topic entry must be a mapping, got {type(entry).__name__}")
        tid = str(entry["id"])
        if tid in seen:
            raise ValueError(f"duplicate topic id: {tid}")
        seen.add(tid)
        out.append(Topic(id=tid, name=str(entry["name"])))
    return tuple(out)


def parse_doc(doc: dict[str, object]) -> NGPatternBook:
    """生 YAML 辞書を NGPatternBook に変換する.

    Phase 7b 以前は `loader._parse` という private 関数だったが,
    共通 schema 化に伴い public API として露出する.
    """
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


def load_ng_pattern_book(path: Path) -> NGPatternBook:
    """任意の YAML ファイルから NG パターン共通 schema をロードする.

    NDA (`ng_patterns.yaml`) と ISO27001 (`audit_findings.yaml`) の
    両方を同じパース経路でロードできることが Phase 7b の合格条件
    (`phase7_design.md` §6.2 第 2 ゲート).
    """
    text = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise ValueError(f"yaml root must be a mapping, got {type(doc).__name__}")
    return parse_doc(doc)
