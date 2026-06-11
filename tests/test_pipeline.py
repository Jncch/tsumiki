"""CleanClause 構築パイプラインのテスト. 小さな docx を tmp_path に作って通す."""

from __future__ import annotations

from pathlib import Path

from docx import Document

from tsumiki.data.pipeline import build_clean_clauses
from tsumiki.data.sources.loader import (
    Source,
    SourceCatalog,
    SourceFile,
)


def _make_docx(path: Path, paragraphs: list[str]) -> None:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    doc.save(str(path))


def _catalog(files: list[SourceFile]) -> SourceCatalog:
    src = Source(
        id="test_src",
        title="t",
        publisher="p",
        landing_page="https://example.test/",
        license="cc0",
        notes="",
        files=tuple(files),
    )
    return SourceCatalog(version="0", last_updated="2026-06-08", sources=(src,))


_LONG_BODY_1 = (
    "本契約は、甲乙間における秘密情報の取扱いに関する基本的な事項を定めるものとし、"
    "両者の権利義務を明確にすることを目的とする。"
)
_LONG_BODY_2 = (
    "秘密情報とは、本契約に基づき開示当事者から受領当事者に対して提供される"
    "技術上又は営業上の情報のうち、秘密として指定されたものをいう。"
)


def test_build_uses_only_existing_clean_files(tmp_path: Path) -> None:
    template_path = tmp_path / "data/raw/nda/test_src/template.docx"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    _make_docx(
        template_path,
        ["第1条（目的）", _LONG_BODY_1, "第2条（範囲）", _LONG_BODY_2],
    )

    files = [
        SourceFile(
            target_path="data/raw/nda/test_src/template.docx",
            url="https://example.test/template.docx",
            kind="nda_template",
            format="docx",
        ),
        SourceFile(
            target_path="data/raw/nda/test_src/missing.docx",
            url="https://example.test/missing.docx",
            kind="nda_template",
            format="docx",
        ),
        SourceFile(
            target_path="data/raw/nda/test_src/commentary.pdf",
            url="https://example.test/commentary.pdf",
            kind="nda_template_with_commentary",
            format="pdf",
        ),
    ]
    catalog = _catalog(files)
    clauses, report = build_clean_clauses(catalog, tmp_path)

    assert report.n_files_used == 1
    assert report.n_files_skipped == 2  # missing + commentary
    assert [c.article_no for c in clauses] == ["1", "2"]
    assert all(c.source_id == "test_src" for c in clauses)
    assert report.n_clauses_raw == 2
    assert report.n_clauses_filtered == 0


def test_build_filters_short_and_option_clauses(tmp_path: Path) -> None:
    """短い署名欄系とオプション条項マーカーは除外."""
    template_path = tmp_path / "data/raw/nda/test_src/template.docx"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    _make_docx(
        template_path,
        [
            "第1条（目的）",
            _LONG_BODY_1,
            "第2条（住所）",
            "東京都",  # too short
            "第3条（オプション）",
            "■■オプション条項■■ 以下は差し替え用条項です。" + _LONG_BODY_2,
        ],
    )
    files = [
        SourceFile(
            target_path="data/raw/nda/test_src/template.docx",
            url="https://example.test/template.docx",
            kind="nda_template",
            format="docx",
        ),
    ]
    catalog = _catalog(files)
    clauses, report = build_clean_clauses(catalog, tmp_path)
    assert report.n_clauses_raw == 3
    assert report.n_clauses_filtered == 2  # short + option
    assert report.n_clauses == 1
    assert [c.article_no for c in clauses] == ["1"]


def test_build_sanitizes_tabs(tmp_path: Path) -> None:
    """テキストからタブが除去されていることを確認."""
    template_path = tmp_path / "data/raw/nda/test_src/template.docx"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    _make_docx(
        template_path,
        ["第1条（目的）", _LONG_BODY_1 + "\t以上のとおりとする。"],
    )
    files = [
        SourceFile(
            target_path="data/raw/nda/test_src/template.docx",
            url="https://example.test/template.docx",
            kind="nda_template",
            format="docx",
        ),
    ]
    catalog = _catalog(files)
    clauses, _ = build_clean_clauses(catalog, tmp_path)
    assert len(clauses) == 1
    assert "\t" not in clauses[0].text
