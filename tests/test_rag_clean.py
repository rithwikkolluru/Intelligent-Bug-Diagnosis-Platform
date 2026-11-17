from __future__ import annotations

from app.rag.clean import clean_records, clean_text


def test_html_stripping_and_normalisation():
    raw = {"title": "  <b>Bug</b> &amp; issue  ", "description": "Line 1\n\nLine 2"}
    cleaned, counts = clean_records([raw])
    assert cleaned[0]["title"] == "Bug & issue"
    assert "Line 1 Line 2" not in cleaned[0]["description"]
    assert counts["initial"] == 1


def test_short_record_dropped():
    records = [{"title": "X", "description": "short"}]
    cleaned, counts = clean_records(records)
    assert cleaned == []
    assert counts["short_records_removed"] == 1


def test_exact_dedupe_removed():
    records = [{"title": "same", "description": "same description"}, {"title": "same", "description": "same description"}]
    cleaned, counts = clean_records(records)
    assert len(cleaned) == 1
    assert counts["duplicate_text_removed"] == 1


def test_clean_text_handles_unicode_and_boilerplate():
    text = "Created attachment\nCaf&#233;\n\nFrom: test@example.com\nStop"
    result = clean_text(text)
    assert "Café" in result or "Cafe" in result
    assert "Created attachment" not in result
