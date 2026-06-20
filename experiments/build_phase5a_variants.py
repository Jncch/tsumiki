"""Phase 5a 辞書 ablation 用の variant YAML を生成する.

ベース辞書 `src/tsumiki/knowledge/nda/ng_patterns.yaml` (version 0.3.0) から、
description の 3 セクション (検出すべき / 紛らわしい / 対象条項)、excerpt_examples、
applicable_topics のうち 1 要素を空にした variant V0〜V5 を作る。

出力:
    src/tsumiki/knowledge/nda/ng_patterns_v0_3_0_V{0..5}.yaml

設計: docs/experiments/phase5a_design.md §1
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "src" / "tsumiki" / "knowledge" / "nda" / "ng_patterns.yaml"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "src" / "tsumiki" / "knowledge" / "nda"
EXPECTED_BASE_VERSION = "0.3.0"

# description セクションヘッダ。ベース辞書での出現順を保持する。
SECTION_KEYS_IN_ORDER: list[str] = ["detect", "confusable", "target_clause"]
SECTION_HEADERS: dict[str, str] = {
    "detect": "検出すべき",
    "confusable": "紛らわしい",
    "target_clause": "対象条項",
}

# (variant_id, drop_section_key, drop_excerpt, drop_topics)
VARIANTS: list[tuple[str, str | None, bool, bool]] = [
    ("V0", None, False, False),
    ("V1", "detect", False, False),
    ("V2", "confusable", False, False),
    ("V3", "target_clause", False, False),
    ("V4", None, True, False),
    ("V5", None, False, True),
]


def split_description(desc: str) -> dict[str, list[str]]:
    """description を 3 セクション + プリアンブルに分割.

    各セクションは「ヘッダ行 + 以降の行」の list[str] を保持する。
    どのセクションにも属さない先頭行は __pre に入る。
    """
    sections: dict[str, list[str]] = {"__pre": []}
    for key in SECTION_KEYS_IN_ORDER:
        sections[key] = []
    current: str | None = None
    for raw_line in desc.splitlines(keepends=True):
        stripped = raw_line.lstrip()
        matched: str | None = None
        for key in SECTION_KEYS_IN_ORDER:
            header = SECTION_HEADERS[key]
            if stripped.startswith(f"{header}:"):
                matched = key
                break
        if matched is not None:
            current = matched
            sections[current].append(raw_line)
        elif current is None:
            sections["__pre"].append(raw_line)
        else:
            sections[current].append(raw_line)
    return sections


def assemble_description(parts: dict[str, list[str]], drop_key: str | None) -> str:
    """drop_key で指定したセクションを除外して description を再構築する."""
    out: list[str] = []
    out.extend(parts["__pre"])
    for key in SECTION_KEYS_IN_ORDER:
        if key == drop_key:
            continue
        out.extend(parts[key])
    return "".join(out)


def make_variant(
    base: dict,
    variant_id: str,
    drop_section: str | None,
    drop_excerpt: bool,
    drop_topics: bool,
) -> dict:
    v = copy.deepcopy(base)
    base_version = v.get("version", "")
    v["version"] = f"{base_version}-{variant_id.lower()}"
    for pattern in v.get("patterns", []):
        if drop_section is not None:
            parts = split_description(pattern.get("description", ""))
            if not parts[drop_section]:
                print(
                    f"[warn] pattern {pattern.get('id')!r} に "
                    f"'{SECTION_HEADERS[drop_section]}:' セクションが見つかりません "
                    f"({variant_id})"
                )
            pattern["description"] = assemble_description(parts, drop_section)
        if drop_excerpt:
            pattern["excerpt_examples"] = []
        if drop_topics:
            pattern["applicable_topics"] = []
    return v


def dump_yaml(data: dict, path: Path) -> None:
    text = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    path.write_text(text, encoding="utf-8")


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
        help=f"variant YAML の出力先 (default: {DEFAULT_OUTPUT_DIR.relative_to(PROJECT_ROOT)})",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.source.is_file():
        print(f"[error] base dictionary not found: {args.source}", file=sys.stderr)
        return 1
    args.output_dir.mkdir(parents=True, exist_ok=True)

    base = yaml.safe_load(args.source.read_text(encoding="utf-8"))
    base_version = base.get("version", "")
    if base_version != EXPECTED_BASE_VERSION:
        print(
            f"[warn] base version is {base_version!r}, expected {EXPECTED_BASE_VERSION!r}. "
            "variant 出力は続行する。"
        )

    for variant_id, drop_section, drop_excerpt, drop_topics in VARIANTS:
        v = make_variant(base, variant_id, drop_section, drop_excerpt, drop_topics)
        out_path = args.output_dir / f"ng_patterns_v0_3_0_{variant_id}.yaml"
        dump_yaml(v, out_path)
        details = []
        if drop_section is not None:
            details.append(f"drop_description_section={SECTION_HEADERS[drop_section]}")
        if drop_excerpt:
            details.append("drop_excerpt_examples")
        if drop_topics:
            details.append("drop_applicable_topics")
        details_str = ", ".join(details) if details else "no drop"
        print(f"[done] {out_path.relative_to(PROJECT_ROOT)}  ({details_str})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
