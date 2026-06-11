"""docx 抽出テスト. テスト用の docx は python-docx で生成する."""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from tsumiki.data.extract import extract_text, extract_text_from_docx


def _make_docx(path: Path, paragraphs: list[str]) -> None:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    doc.save(str(path))


def test_extract_text_from_docx_strips_blank(tmp_path: Path) -> None:
    p = tmp_path / "sample.docx"
    _make_docx(p, ["第1条", "", "本契約は…", "  ", "第2条"])
    text = extract_text_from_docx(p)
    assert text == "第1条\n本契約は…\n第2条"


def test_extract_dispatch_by_suffix(tmp_path: Path) -> None:
    p = tmp_path / "sample.DOCX"
    _make_docx(p, ["hello"])
    assert extract_text(p).strip() == "hello"


def test_extract_unsupported_format(tmp_path: Path) -> None:
    p = tmp_path / "sample.txt"
    p.write_text("dummy", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        extract_text(p)
