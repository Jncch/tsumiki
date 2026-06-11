"""配置済みの雛形 NDA から CleanClause JSONL を組み立てる.

使い方:
    uv run python experiments/build_clean_clauses.py
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from tsumiki.data.pipeline import build_clean_clauses
from tsumiki.data.sources.loader import load_nda_templates_catalog

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = PROJECT_ROOT / "data" / "processed" / "nda_clean_clauses.jsonl"


def main() -> int:
    catalog = load_nda_templates_catalog()
    clauses, report = build_clean_clauses(catalog, PROJECT_ROOT)
    print(
        f"[build] files used={report.n_files_used} "
        f"skipped={report.n_files_skipped} "
        f"clauses={report.n_clauses}"
    )
    if not clauses:
        print("[build] no clauses produced — 雛形ファイルが未配置の可能性があります.")
        print(
            "  src/tsumiki/data/sources/nda_templates.yaml の URL から保存して再実行してください."
        )
        return 1
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for c in clauses:
            fh.write(json.dumps(asdict(c), ensure_ascii=False))
            fh.write("\n")
    print(f"[build] wrote {len(clauses)} clauses to {OUT_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
