"""条単位セグメンタのテスト."""

from __future__ import annotations

from tsumiki.data.segment import segment_clauses


def test_basic_segmentation() -> None:
    text = (
        "第1条（目的）\n本契約は、甲乙間における…\n\n"
        "第2条（秘密情報）\n1. 本契約において…\n2. 前項に関わらず…\n\n"
        "第3条（秘密保持義務）\n受領当事者は…"
    )
    clauses = segment_clauses(text, source_id="src1")
    assert [c.article_no for c in clauses] == ["1", "2", "3"]
    assert clauses[0].clause_id == "src1:1"
    assert clauses[1].text.startswith("第2条")
    assert "前項に関わらず" in clauses[1].text


def test_fullwidth_article_no_normalized() -> None:
    text = "第１条（目的）\n本文。\n\n第２条（範囲）\n本文。"
    clauses = segment_clauses(text, source_id="src2")
    assert [c.article_no for c in clauses] == ["1", "2"]


def test_no_articles_returns_empty() -> None:
    assert segment_clauses("前文のみ。", source_id="src3") == []


def test_duplicate_article_no_gets_suffix() -> None:
    # 第2条 が 2 回出てくる崩れた契約への耐性
    text = "第1条\n本文1\n\n第2条\n本文2a\n\n第2条\n本文2b"
    clauses = segment_clauses(text, source_id="src4")
    assert [c.clause_id for c in clauses] == ["src4:1", "src4:2", "src4:2#2"]


def test_clause_text_preserves_subitems() -> None:
    text = "第2条（秘密情報）\n1. A\n2. B\n3. C"
    clauses = segment_clauses(text, source_id="src5")
    assert len(clauses) == 1
    body = clauses[0].text
    assert "1. A" in body and "2. B" in body and "3. C" in body


def test_bracket_title_only_format() -> None:
    """中小企業庁 NDA ひな形のように `第N条` が無く `（タイトル）` のみの形式."""
    text = (
        "秘密保持契約書\n"
        "甲及び乙は次の通り…\n"
        "（目的）\n"
        "甲及び乙は、検討を目的として…\n"
        "（定義）\n"
        "１　「秘密情報」とは…\n"
        "（秘密保持義務）\n"
        "受領者は…\n"
    )
    clauses = segment_clauses(text, source_id="src6")
    assert [c.article_no for c in clauses] == ["1", "2", "3"]
    assert "目的" in clauses[0].text
    assert "「秘密情報」" in clauses[1].text


def test_inline_bracketed_phrase_is_not_a_header() -> None:
    """文中の括弧書きは header と誤認しない（行末でない括弧は対象外）."""
    text = "（目的）\n甲及び乙（以下「両社」という）は…\n（範囲）\n…"
    clauses = segment_clauses(text, source_id="src7")
    # 2 件のみ（「以下「両社」という」を見出しと誤認しない）
    assert len(clauses) == 2
    assert "両社" in clauses[0].text


def test_article_format_takes_priority_over_bracket() -> None:
    text = "第1条（目的）\n本契約は…\n（補足）\nなお…"
    clauses = segment_clauses(text, source_id="src8")
    # 第N条 ヒットしたので 1 件、補足はその本文に含まれる
    assert len(clauses) == 1
    assert clauses[0].article_no == "1"
    assert "（補足）" in clauses[0].text
