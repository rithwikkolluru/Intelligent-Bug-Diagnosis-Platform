from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.bug import BugReport
from app.services.parsing import ParsingError, parse_upload
from app.services.redaction import redact_secrets
from app.services.stacktrace import detect_and_split


class SubmissionError(ValueError):
    def __init__(self, message: str, code: str = "INVALID_FIELD"):
        self.message = message
        self.code = code


def validate_bug_payload(data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        raise SubmissionError("Input body is empty.", "EMPTY_INPUT")

    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    if not title:
        raise SubmissionError("Title is required.", "INVALID_FIELD")
    if len(title) < 3 or len(title) > 300:
        raise SubmissionError("Title must be between 3 and 300 characters.", "INVALID_FIELD")
    if not description:
        raise SubmissionError("Description is required.", "EMPTY_INPUT")
    if len(description) < 10:
        raise SubmissionError("Description must be at least 10 characters long.", "INVALID_FIELD")

    return {
        "title": title,
        "description": description,
        "stack_trace": data.get("stack_trace"),
        "error_logs": data.get("error_logs"),
        "programming_language": data.get("programming_language"),
    }


def create_bug_record(db: Session, payload: dict[str, Any], source_type: str, original_filename: str | None = None) -> BugReport:
    title = str(payload.get("title", "")).strip()
    description = str(payload.get("description", "")).strip()
    stack_trace = str(payload.get("stack_trace", "") or "").strip() or None
    error_logs = str(payload.get("error_logs", "") or "").strip() or None
    programming_language = str(payload.get("programming_language", "") or "").strip() or None

    if not title or not description:
        raise SubmissionError("Title and description are required.", "INVALID_FIELD")

    if stack_trace:
        description_no_trace, trace, language_guess = detect_and_split(description + "\n" + stack_trace)
        if trace:
            description = description_no_trace or description
            stack_trace = trace
            if programming_language is None and language_guess:
                programming_language = language_guess
    elif error_logs:
        description_no_trace, trace, language_guess = detect_and_split(error_logs)
        if trace:
            description = description_no_trace or description
            stack_trace = trace
            if programming_language is None and language_guess:
                programming_language = language_guess

    description, d_count = redact_secrets(description)
    stack_trace, s_count = redact_secrets(stack_trace) if stack_trace else (None, 0)
    error_logs, e_count = redact_secrets(error_logs) if error_logs else (None, 0)
    redaction_count = d_count + s_count + e_count

    bug = BugReport(
        title=title[:300],
        description=description,
        stack_trace=stack_trace,
        error_logs=error_logs,
        programming_language=programming_language,
        source_type=source_type,
        original_filename=original_filename,
        status="received",
        redaction_count=redaction_count,
    )
    db.add(bug)
    db.commit()
    db.refresh(bug)
    return bug


def handle_uploaded_file(db: Session, file: UploadFile, title: str | None = None, programming_language: str | None = None) -> BugReport:
    if not file.filename:
        raise SubmissionError("Uploaded file is missing a filename.", "INVALID_FIELD")

    safe_filename = Path(file.filename).name
    suffix = Path(safe_filename).suffix.lower()
    settings = get_settings()

    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise SubmissionError(f"Unsupported file extension: {suffix}", "UNSUPPORTED_FILE_TYPE")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    content = file.file.read(max_bytes + 1)
    if not content or not content.strip():
        raise SubmissionError("Uploaded file is empty.", "EMPTY_INPUT")
    if len(content) > max_bytes:
        raise SubmissionError(f"Uploaded file exceeds maximum allowed size of {settings.MAX_UPLOAD_MB} MB.", "FILE_TOO_LARGE")

    try:
        parsed = parse_upload(safe_filename, content)
    except ParsingError as exc:
        raise SubmissionError(exc.message, exc.code) from exc

    payload = {
        "title": title or parsed.get("title") or "Uploaded issue",
        "description": parsed.get("description") or "Uploaded bug report.",
        "stack_trace": parsed.get("stack_trace"),
        "error_logs": parsed.get("error_logs"),
        "programming_language": programming_language or parsed.get("programming_language"),
    }
    if len(str(payload["title"]).strip()) < 3:
        raise SubmissionError("Title must be at least 3 characters long.", "INVALID_FIELD")
    return create_bug_record(db, payload, source_type="upload", original_filename=safe_filename)
