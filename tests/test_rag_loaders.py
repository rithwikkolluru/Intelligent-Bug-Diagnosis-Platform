from __future__ import annotations

from pathlib import Path

from app.rag.loaders import BaseLoader


def test_fixture_loader_reads_realistic_rows():
    base = Path(__file__).resolve().parent / "fixtures"
    loader = BaseLoader(base_dir=base)
    rows = loader.iter_records()
    records = list(rows)
    assert len(records) >= 3
    assert any(row.get("project") == "mozilla" for row in records)
    assert any(row.get("project") == "eclipse" for row in records)
    assert any(row.get("project") == "apache" for row in records)
