from __future__ import annotations

from app.rag.standardise import HistoricalDefect, standardise_records


def test_id_namespacing_and_vocab_mapping():
    records = [{
        "project": "mozilla",
        "id": "123",
        "title": "Crash on start",
        "description": "The app crashes on startup.",
        "severity": "Major",
        "priority": "P1",
        "status": "Fixed",
        "resolution": "Duplicate",
        "stack_trace": "java.lang.RuntimeException",
    }]
    defects = standardise_records(records)
    assert defects[0].defect_id == "mozilla-123"
    assert defects[0].severity == "major"
    assert defects[0].priority == "p1"
    assert defects[0].status == "fixed"
    assert defects[0].resolution == "duplicate"
    assert defects[0].has_stack_trace is True


def test_model_validation_roundtrip():
    defect = HistoricalDefect(
        defect_id="apache-A1",
        original_id="A1",
        project="apache",
        summary="Issue",
        description="Problem description",
        stack_trace="Exception: boom",
        comments=[{"author_role_or_id": "triage", "text": "Reproduced", "timestamp": None}],
    )
    assert defect.as_index_record["project"] == "apache"
    assert defect.as_index_record["has_stack_trace"] is True
