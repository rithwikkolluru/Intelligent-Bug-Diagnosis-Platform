from __future__ import annotations

from app.rag.chunking import chunk_defect, chunk_records
from app.rag.standardise import HistoricalDefect


def test_chunk_ids_unique_and_metadata_valid():
    defect = HistoricalDefect(
        defect_id="mozilla-123",
        original_id="123",
        project="mozilla",
        summary="Crash on start",
        description="The app crashes on startup when login is called.",
        stack_trace="java.lang.RuntimeException\n    at a.b.c(Thing.java:12)\nCaused by: java.lang.IllegalStateException",
        comments=[{"author_role_or_id": "triage", "text": "This occurs only in prod."}],
        severity="major",
        priority="p2",
        status="open",
        resolution="fixed",
        source_url="https://example.com",
        has_stack_trace=True,
    )
    chunks = chunk_defect(defect, max_tokens=50, overlap=10, min_comment_length=5)
    assert len(chunks) >= 3
    assert len({chunk["chunk_id"] for chunk in chunks}) == len(chunks)
    for chunk in chunks:
        metadata = chunk["metadata"]
        assert isinstance(metadata["project"], str)
        assert isinstance(metadata["has_stack_trace"], bool)


def test_stack_trace_chunk_not_split():
    defect = HistoricalDefect(
        defect_id="eclipse-E1",
        original_id="E1",
        project="eclipse",
        summary="Trace issue",
        description="The app crashes.",
        stack_trace="Traceback (most recent call last):\n  File \"x.py\", line 1\nValueError: boom",
    )
    chunks = chunk_records([defect], max_tokens=10, overlap=0, min_comment_length=5)
    stack_chunks = [chunk for chunk in chunks if chunk["chunk_type"] == "stack_trace"]
    assert len(stack_chunks) == 1
    assert "ValueError" in stack_chunks[0]["text"]
