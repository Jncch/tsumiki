#!/usr/bin/env python
"""NDA 雛形ファイルが期待パスに配置されているかを確認する.

未配置ファイルがあれば、出典 URL とダウンロード先パスを出して終了コード 1。
"""

from __future__ import annotations

import sys
from pathlib import Path

from tsumiki.data.sources.loader import load_nda_templates_catalog

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    catalog = load_nda_templates_catalog()
    missing: list[tuple[str, str, str]] = []
    present: list[tuple[str, str, int]] = []
    for source in catalog.sources:
        for f in source.files:
            if f.exists(PROJECT_ROOT):
                size = f.size_bytes(PROJECT_ROOT) or 0
                present.append((source.id, f.target_path, size))
            else:
                missing.append((source.id, f.target_path, f.url))

    if present:
        print(f"[check] 配置済み {len(present)} 件:")
        for source_id, path, size in present:
            print(f"  [{source_id}] {path}  ({size:,} bytes)")
    if missing:
        print(f"\n[check] 未配置 {len(missing)} 件 — ブラウザで保存してください:")
        for source_id, path, url in missing:
            print(f"  [{source_id}]")
            print(f"    保存先: {path}")
            print(f"    URL:    {url}")
        return 1
    print("\n[check] すべてのファイルが配置済み.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
