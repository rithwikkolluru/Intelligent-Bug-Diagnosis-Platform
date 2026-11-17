from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from app.rag.standardise import HistoricalDefect


def _token_count(text: str) -> int:
    return max(1, len(re.findall(r"\S+", text)))


def _make_chunk_id(defect_id: str, chunk_type: str, idx: int) -> str:
    return f"{defect_id}::{chunk_type}::{idx}"


def _sanitize_metadata(defect: HistoricalDefect, **extra: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "project": defect.project,
        "component": defect.component or "",
        "severity": defect.severity,
        "priority": defect.priority,
        "status": defect.status,
        "resolution": defect.resolution,
        "has_stack_trace": bool(defect.has_stack_trace),
        "source_url": defect.source_url or "",
        "created_year": defect.created_at.year if defect.created_at else 0,
    }
    metadata.update(extra)
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            cleaned[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)
    return cleaned


def chunk_description(defect: HistoricalDefect, max_tokens: int = 350, overlap: int = 50) -> list[dict[str, Any]]:
    text = "\n\n".join(part for part in [defect.summary, defect.description] if part).strip()
    if not text:
        return []
    chunks: list[dict[str, Any]] = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    current: list[str] = []
    current_tokens = 0
    for paragraph in paragraphs:
        para_tokens = _token_count(paragraph)
        if current and current_tokens + para_tokens > max_tokens:
            body = "\n\n".join(current)
            chunks.append({
                "chunk_id": _make_chunk_id(defect.defect_id, "description", len(chunks)),
                "defect_id": defect.defect_id,
                "chunk_type": "description",
                "text": body,
                "token_count": _token_count(body),
                "metadata": _sanitize_metadata(defect),
            })
            current = [paragraph]
            current_tokens = para_tokens
        else:
            current.append(paragraph)
            current_tokens += para_tokens
    if current:
        body = "\n\n".join(current)
        chunks.append({
            "chunk_id": _make_chunk_id(defect.defect_id, "description", len(chunks)),
            "defect_id": defect.defect_id,
            "chunk_type": "description",
            "text": body,
            "token_count": _token_count(body),
            "metadata": _sanitize_metadata(defect),
        })
    if overlap > 0 and len(chunks) > 1:
        shifted = []
        for i, chunk in enumerate(chunks):
            if i == 0:
                shifted.append(chunk)
                continue
            prev = chunks[i - 1]["text"]
            tail = prev.split()[-max(1, overlap):]
            chunk["text"] = (" ".join(tail) + " " + chunk["text"]).strip()
            chunk["token_count"] = _token_count(chunk["text"])
            shifted.append(chunk)
        return shifted
    return chunks


def chunk_stack_trace(defect: HistoricalDefect) -> list[dict[str, Any]]:
    trace = defect.stack_trace or ""
    if not trace:
        return []
    lines = [line.rstrip() for line in trace.splitlines() if line.strip()]
    if not lines:
        return []
    first_line = lines[0]
    exception_lines = [first_line]
    cause_lines = []
    for line in lines[1:]:
        if "Caused by:" in line or "caused by:" in line:
            cause_lines.append(line)
        elif line.startswith("at ") or "" in line:
            exception_lines.append(line)
    text = "\n".join(exception_lines + cause_lines)
    return [{
        "chunk_id": _make_chunk_id(defect.defect_id, "stack_trace", 0),
        "defect_id": defect.defect_id,
        "chunk_type": "stack_trace",
        "text": text,
        "token_count": _token_count(text),
        "metadata": _sanitize_metadata(defect),
    }]


def chunk_comments(defect: HistoricalDefect, min_comment_length: int = 30) -> list[dict[str, Any]]:
    comments = defect.comments or []
    if not comments:
        return []
    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    current_count = 0
    for comment in comments:
        text = str(comment.get("text") or "").strip()
        if len(text) < min_comment_length:
            continue
        current.append(text)
        current_count += len(text)
        if current_count > 350:
            body = "\n".join(current)
            chunks.append({
                "chunk_id": _make_chunk_id(defect.defect_id, "comment", len(chunks)),
                "defect_id": defect.defect_id,
                "chunk_type": "comment",
                "text": body,
                "token_count": _token_count(body),
                "metadata": _sanitize_metadata(defect),
            })
            current = []
            current_count = 0
    if current:
        body = "\n".join(current)
        chunks.append({
            "chunk_id": _make_chunk_id(defect.defect_id, "comment", len(chunks)),
            "defect_id": defect.defect_id,
            "chunk_type": "comment",
            "text": body,
            "token_count": _token_count(body),
            "metadata": _sanitize_metadata(defect),
        })
    return chunks


def chunk_resolution(defect: HistoricalDefect) -> list[dict[str, Any]]:
    if not defect.resolution_text:
        return []
    text = f"{defect.resolution or 'resolution'}\n{defect.resolution_text}".strip()
    return [{
        "chunk_id": _make_chunk_id(defect.defect_id, "resolution", 0),
        "defect_id": defect.defect_id,
        "chunk_type": "resolution",
        "text": text,
        "token_count": _token_count(text),
        "metadata": _sanitize_metadata(defect),
    }]


def chunk_defect(defect: HistoricalDefect, *, max_tokens: int = 350, overlap: int = 50, min_comment_length: int = 30) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    chunks.extend(chunk_description(defect, max_tokens=max_tokens, overlap=overlap))
    chunks.extend(chunk_stack_trace(defect))
    chunks.extend(chunk_comments(defect, min_comment_length=min_comment_length))
    chunks.extend(chunk_resolution(defect))
    return chunks


def chunk_records(defects: Iterable[HistoricalDefect], *, max_tokens: int = 350, overlap: int = 50, min_comment_length: int = 30) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for defect in defects:
        chunks.extend(chunk_defect(defect, max_tokens=max_tokens, overlap=overlap, min_comment_length=min_comment_length))
    return chunks
