from __future__ import annotations

import html
import re
from collections.abc import Iterable
from typing import Any

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
EMAIL_HEADER_RE = re.compile(r"(?im)^((from|to|cc|subject|date|reply-to|sender|content-type):.*)$")
ATTACHMENT_RE = re.compile(r"(?i)created attachment.*?", re.DOTALL)


def clean_text(value: Any, *, preserve_newlines: bool = False) -> str:
    if value is None:
        return ""
    text = str(value)
    text = html.unescape(text)
    text = HTML_TAG_RE.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = EMAIL_HEADER_RE.sub(" ", text)
    text = ATTACHMENT_RE.sub(" ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = WHITESPACE_RE.sub(" ", text).strip() if not preserve_newlines else re.sub(r"[ \t]+", " ", text).strip()
    return text


def remove_duplicate_text(records: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[str] = set()
    unique_records: list[dict[str, Any]] = []
    removed = 0
    for record in records:
        key = "\n".join(
            str(record.get(field, ""))
            for field in ("summary", "title", "description", "body", "text")
            if record.get(field) is not None
        )
        if not key:
            unique_records.append(record)
            continue
        key = clean_text(key)
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        unique_records.append(record)
    return unique_records, removed


def clean_records(records: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    counts = {
        "initial": 0,
        "short_records_removed": 0,
        "duplicate_text_removed": 0,
        "boilerplate_removed": 0,
        "empty_after_cleaning": 0,
    }
    cleaned: list[dict[str, Any]] = []
    for record in records:
        counts["initial"] += 1
        summary = clean_text(record.get("summary") or record.get("title") or "")
        description = clean_text(record.get("description") or record.get("body") or "", preserve_newlines=True)
        description = re.sub(r"\n\s*\n+", "\n\n", description)
        if not summary and not description:
            counts["empty_after_cleaning"] += 1
            continue
        if len(summary.strip()) < 3 and len(description.strip()) < 10:
            counts["short_records_removed"] += 1
            continue
        record = dict(record)
        record["summary"] = summary
        record["description"] = description
        record["title"] = summary or record.get("title") or "Untitled defect"
        if record.get("stack_trace") is not None:
            record["stack_trace"] = clean_text(record["stack_trace"], preserve_newlines=True)
        cleaned.append(record)
    unique_clean, duplicate_count = remove_duplicate_text(cleaned)
    counts["duplicate_text_removed"] = duplicate_count
    return unique_clean, counts
