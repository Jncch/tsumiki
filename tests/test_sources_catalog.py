"""NDA 雛形カタログ（出典メタデータ）のロードテスト."""

from __future__ import annotations

import pytest

from tsumiki.data.sources.loader import load_nda_templates_catalog


def test_load_catalog() -> None:
    catalog = load_nda_templates_catalog()
    assert catalog.version
    assert catalog.last_updated
    assert len(catalog.sources) >= 3
    ids = [s.id for s in catalog.sources]
    assert len(ids) == len(set(ids))  # 一意


def test_each_source_has_files() -> None:
    catalog = load_nda_templates_catalog()
    for source in catalog.sources:
        assert source.title and source.publisher
        assert source.license
        assert len(source.files) >= 1
        for f in source.files:
            assert f.target_path.startswith("data/raw/nda/")
            assert f.url.startswith("https://")
            assert f.format in ("pdf", "docx", "txt")


def test_by_id_missing_raises() -> None:
    catalog = load_nda_templates_catalog()
    with pytest.raises(KeyError):
        catalog.by_id("does_not_exist")
