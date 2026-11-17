from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.services.stacktrace import detect_and_split


class ParsingError(ValueError):
    def __init__(self, message: str, code: str = "MALFORMED_FILE"):
        self.message = message
        self.code = code


def _decode_text(raw: bytes) -> tuple[str, str | None]:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding), None if encoding != "latin-1" else "Decoded with latin-1 fallback."
        except UnicodeDecodeError:
            continue
    raise ParsingError("Unable to decode uploaded file.", "MALFORMED_FILE")


def _parse_json_text(content: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ParsingError(f"Malformed JSON: {exc.msg}", "MALFORMED_FILE") from exc

    if isinstance(payload, list):
        if not payload:
            raise ParsingError("JSON list is empty.", "MALFORMED_FILE")
        payload = payload[0]
    if not isinstance(payload, dict):
        raise ParsingError("JSON payload must be an object or list of objects.", "MALFORMED_FILE")
    return payload


def _parse_csv_text(content: str) -> dict[str, Any]:
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise ParsingError("CSV file is missing a header row.", "MALFORMED_FILE")
    row = next(reader, None)
    if row is None:
        raise ParsingError("CSV file is empty or missing data rows.", "MALFORMED_FILE")
    missing_values = any(value is None or str(value).strip() == "" for value in row.values())
    if missing_values:
        raise ParsingError("CSV row is incomplete or malformed.", "MALFORMED_FILE")
    return {key: value for key, value in row.items() if key is not None}


def parse_upload(filename: str, content_bytes: bytes) -> dict[str, Any]:
    if not filename:
        raise ParsingError("Missing filename.", "MALFORMED_FILE")

    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    text, fallback_note = _decode_text(content_bytes)

    if suffix in {"txt", "log", "md"}:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise ParsingError("Uploaded file is empty.", "MALFORMED_FILE")
        title = lines[0][:300]
        description = "\n".join(lines[1:]) if len(lines) > 1 else "Uploaded log without additional prose."
        description = description.strip() or "Uploaded log without additional prose."
        _, trace, lang = detect_and_split(text)
        return {
            "title": title,
            "description": description,
            "stack_trace": trace,
            "error_logs": text,
            "programming_language": lang,
            "source_type": "upload",
            "original_filename": filename,
            "note": fallback_note,
        }

    if suffix == "json":
        payload = _parse_json_text(text)
        clean = {
            "title": payload.get("title") or payload.get("summary") or payload.get("bug_title") or "Imported bug",
            "description": payload.get("description") or payload.get("body") or payload.get("details") or "Imported bug description.",
            "stack_trace": payload.get("stack_trace") or payload.get("stacktrace") or None,
            "error_logs": payload.get("logs") or payload.get("error_logs") or payload.get("log") or None,
            "programming_language": payload.get("language") or payload.get("programming_language") or None,
        }
        return {
            **clean,
            "source_type": "upload",
            "original_filename": filename,
            "note": fallback_note,
        }

    if suffix == "csv":
        payload = _parse_csv_text(text)
        clean = {
            "title": payload.get("title") or payload.get("summary") or "Imported CSV bug",
            "description": payload.get("description") or payload.get("body") or payload.get("details") or "Imported CSV bug description.",
            "stack_trace": payload.get("stack_trace") or payload.get("stacktrace") or None,
            "error_logs": payload.get("logs") or payload.get("error_logs") or payload.get("log") or None,
            "programming_language": payload.get("language") or payload.get("programming_language") or None,
        }
        return {
            **clean,
            "source_type": "upload",
            "original_filename": filename,
            "note": fallback_note,
        }

    raise ParsingError(f"Unsupported file extension: .{suffix}", "UNSUPPORTED_FILE_TYPE")
