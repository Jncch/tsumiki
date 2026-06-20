"""NDA NG パターン YAML を Agent Skills 標準（Markdown スキル）に変換する.

設計: docs/experiments/phase5b_design.md §2

出力:
    src/tsumiki/knowledge/skills/nda/ng_patterns/
        ├── <pattern_id>.md       # 1 スキル = 1 NG パターン
        ├── _index.yaml           # スキル一覧
        └── topics.yaml           # 主題語彙（v0.5.0 prompt 用）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "src" / "tsumiki" / "knowledge" / "nda" / "ng_patterns.yaml"
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "src" / "tsumiki" / "knowledge" / "skills" / "nda" / "ng_patterns"
)
SCHEMA_VERSION = 1
DEFAULT_TASK_CLASSES = ["detect", "modify"]

# description の各セクションヘッダ。Markdown 本文の H2 と同名。
SECTION_HEADERS: tuple[str, ...] = ("対象条項", "検出すべき", "紛らわしい")
# Markdown 本文での表示順
SECTION_ORDER_MD: tuple[str, ...] = ("対象条項", "検出すべき", "紛らわしい")


def split_description(desc: str) -> dict[str, str]:
    """description を各セクションに分割し、ヘッダを除いた本文文字列を返す.

    各セクションは「<ヘッダ>: <本文>」形式で 1 セクション = 1 〜数行。
    複数行になるセクションがあっても次の既知ヘッダまでをそのセクションの本文と見なす。
    """
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in desc.splitlines():
        stripped = line.lstrip()
        matched: str | None = None
        for header in SECTION_HEADERS:
            if stripped.startswith(f"{header}:"):
                matched = header
                content_after = stripped[len(header) + 1 :].lstrip()
                sections.setdefault(matched, [])
                if content_after:
                    sections[matched].append(content_after)
                break
        if matched is not None:
            current = matched
        elif current is not None:
            sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def build_frontmatter(
    pattern: dict, *, domain: str, last_updated: str, maintainer: str
) -> dict:
    fm: dict[str, object] = {
        "id": pattern["id"],
        "name": pattern["name"],
        "domain": domain,
        "schema_version": SCHEMA_VERSION,
        "task_classes": list(DEFAULT_TASK_CLASSES),
    }
    if pattern.get("severity"):
        fm["severity"] = pattern["severity"]
    applicable_topics = pattern.get("applicable_topics") or []
    if applicable_topics:
        fm["applicable_topics"] = list(applicable_topics)
    references = pattern.get("references") or []
    if references:
        fm["references"] = list(references)
    if last_updated:
        fm["last_updated"] = last_updated
    if maintainer:
        fm["maintainer"] = maintainer
    return fm


def render_skill_markdown(
    pattern: dict, *, domain: str, last_updated: str, maintainer: str
) -> str:
    fm = build_frontmatter(
        pattern, domain=domain, last_updated=last_updated, maintainer=maintainer
    )
    fm_yaml = yaml.safe_dump(
        fm, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).strip()
    sections = split_description(pattern.get("description", ""))

    parts: list[str] = ["---", fm_yaml, "---", "", f"# {pattern['name']}", ""]
    for section_name in SECTION_ORDER_MD:
        body = sections.get(section_name, "").strip()
        parts.append(f"## {section_name}")
        parts.append("")
        if body:
            parts.append(body)
            parts.append("")
    parts.append("## 例")
    parts.append("")
    for ex in pattern.get("excerpt_examples", []) or []:
        parts.append(f"- {ex}")
    parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def write_index(
    output_dir: Path, source_version: str, patterns: list[dict], domain: str
) -> None:
    index = {
        "domain": domain,
        "source_version": source_version,
        "schema_version": SCHEMA_VERSION,
        "skills": [
            {"id": p["id"], "file": f"{p['id']}.md", "name": p["name"]}
            for p in patterns
        ],
    }
    path = output_dir / "_index.yaml"
    path.write_text(
        yaml.safe_dump(
            index, allow_unicode=True, sort_keys=False, default_flow_style=False
        ),
        encoding="utf-8",
    )


def write_topics(
    output_dir: Path,
    topics: list[dict],
    *,
    source_version: str,
    last_updated: str,
) -> None:
    out: dict[str, object] = {
        "source_version": source_version,
        "last_updated": last_updated,
        "topics": [{"id": t["id"], "name": t["name"]} for t in topics],
    }
    path = output_dir / "topics.yaml"
    path.write_text(
        yaml.safe_dump(out, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"ベース辞書 YAML (default: {DEFAULT_SOURCE.relative_to(PROJECT_ROOT)})",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Agent Skills 出力ディレクトリ (default: {DEFAULT_OUTPUT_DIR.relative_to(PROJECT_ROOT)})",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    # CLI から相対パスを渡された場合に out_path.relative_to(PROJECT_ROOT) が失敗するのを防ぐ.
    args.source = args.source.resolve()
    args.output_dir = args.output_dir.resolve()
    if not args.source.is_file():
        print(f"[error] source not found: {args.source}", file=sys.stderr)
        return 1
    args.output_dir.mkdir(parents=True, exist_ok=True)

    base = yaml.safe_load(args.source.read_text(encoding="utf-8"))
    domain = str(base.get("contract_type") or "unknown")
    last_updated = str(base.get("last_updated", ""))
    maintainer = str(base.get("maintainer", ""))
    source_version = str(base.get("version", ""))
    topics = base.get("topics", []) or []
    patterns = base.get("patterns", []) or []

    for p in patterns:
        md = render_skill_markdown(
            p, domain=domain, last_updated=last_updated, maintainer=maintainer
        )
        out_path = args.output_dir / f"{p['id']}.md"
        out_path.write_text(md, encoding="utf-8")
        print(f"[done] {out_path.relative_to(PROJECT_ROOT)}")

    write_index(args.output_dir, source_version, patterns, domain)
    print(f"[done] {(args.output_dir / '_index.yaml').relative_to(PROJECT_ROOT)}")

    if topics:
        write_topics(
            args.output_dir,
            topics,
            source_version=source_version,
            last_updated=last_updated,
        )
        print(f"[done] {(args.output_dir / 'topics.yaml').relative_to(PROJECT_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
