from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


SEVERITY_MAP = {
    "blocker": "blocker",
    "critical": "critical",
    "major": "major",
    "normal": "normal",
    "minor": "minor",
    "trivial": "trivial",
    "urgent": "critical",
    "default": "unknown",
}

PRIORITY_MAP = {
    "p1": "p1",
    "p2": "p2",
    "p3": "p3",
    "p4": "p4",
    "p5": "p5",
    "highest": "p1",
    "high": "p2",
    "medium": "p3",
    "low": "p4",
    "lowest": "p5",
    "default": "unknown",
}

STATUS_MAP = {
    "fixed": "fixed",
    "resolved": "fixed",
    "closed": "fixed",
    "verified": "fixed",
    "duplicate": "duplicate",
    "wontfix": "wontfix",
    "won't fix": "wontfix",
    "invalid": "invalid",
    "open": "open",
    "new": "new",
    "reopened": "reopened",
    "default": "unknown",
}

RESOLUTION_MAP = {
    "fixed": "fixed",
    "duplicate": "duplicate",
    "invalid": "invalid",
    "wontfix": "wontfix",
    "won't fix": "wontfix",
    "worksforme": "worksforme",
    "not a bug": "not_a_bug",
    "default": "unknown",
}


class HistoricalDefect(BaseModel):
    defect_id: str
    original_id: str
    project: str = Field(default="mozilla")
    component: str | None = None
    summary: str
    description: str
    stack_trace: str | None = None
    comments: list[dict[str, Any]] = Field(default_factory=list)
    severity: str = "unknown"
    priority: str = "unknown"
    status: str = "unknown"
    resolution: str = "unknown"
    resolution_text: str | None = None
    duplicate_of: str | None = None
    created_at: datetime | None = None
    resolved_at: datetime | None = None
    source_url: str | None = None
    has_stack_trace: bool = False

    @field_validator("project")
    @classmethod
    def validate_project(cls, value: str) -> str:
        return str(value).lower()

    @field_validator("severity", "priority", "status", "resolution")
    @classmethod
    def normalize_enum(cls, value: str | None, info) -> str:
        raw = str(value or "unknown").strip().lower()
        mapping = {
            "severity": SEVERITY_MAP,
            "priority": PRIORITY_MAP,
            "status": STATUS_MAP,
            "resolution": RESOLUTION_MAP,
        }[info.field_name]
        return mapping.get(raw, "unknown")

    @model_validator(mode="after")
    def _sync_stack_trace_flag(self) -> "HistoricalDefect":
        self.has_stack_trace = bool(self.stack_trace) or bool(self.has_stack_trace)
        return self

    @property
    def as_index_record(self) -> dict[str, Any]:
        return {
            "defect_id": self.defect_id,
            "project": self.project,
            "component": self.component or "",
            "summary": self.summary,
            "description": self.description,
            "stack_trace": self.stack_trace or "",
            "severity": self.severity,
            "priority": self.priority,
            "status": self.status,
            "resolution": self.resolution,
            "source_url": self.source_url or "",
            "has_stack_trace": bool(self.stack_trace) or self.has_stack_trace,
        }


def _parse_comments(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        comments = []
        for item in raw:
            if isinstance(item, dict):
                comments.append({
                    "author_role_or_id": item.get("author") or item.get("author_role_or_id") or "unknown",
                    "text": str(item.get("text") or item.get("comment") or "").strip(),
                    "timestamp": item.get("timestamp"),
                })
        return [c for c in comments if c["text"]]
    if isinstance(raw, dict):
        return [{"author_role_or_id": str(raw.get("author") or "unknown"), "text": str(raw.get("text") or raw.get("comment") or "").strip(), "timestamp": raw.get("timestamp")}]
    return [{"author_role_or_id": "unknown", "text": str(raw).strip(), "timestamp": None}]


def standardise_records(records: list[dict[str, Any]]) -> list[HistoricalDefect]:
    defects: list[HistoricalDefect] = []
    seen: set[str] = set()
    for raw in records:
        project = str(raw.get("project") or raw.get("source") or "mozilla").lower()
        original_id = str(raw.get("original_id") or raw.get("issue_id") or raw.get("id") or raw.get("bug_id") or "unknown")
        summary = str(raw.get("summary") or raw.get("title") or raw.get("name") or "").strip()
        description = str(raw.get("description") or raw.get("body") or raw.get("details") or summary).strip()
        stack_trace = raw.get("stack_trace") or raw.get("trace") or raw.get("stacktrace")
        if stack_trace is not None:
            stack_trace = str(stack_trace).strip() or None
        defect_id = f"{project}-{original_id}"
        if defect_id in seen:
            continue
        seen.add(defect_id)
        defect = HistoricalDefect(
            defect_id=defect_id,
            original_id=str(original_id),
            project=project,
            component=str(raw.get("component") or raw.get("product") or None),
            summary=summary or "Untitled defect",
            description=description or summary or "No description available.",
            stack_trace=stack_trace,
            comments=_parse_comments(raw.get("comments") or raw.get("comment") or []),
            severity=str(raw.get("severity") or raw.get("priority_level") or "unknown"),
            priority=str(raw.get("priority") or raw.get("importance") or "unknown"),
            status=str(raw.get("status") or "unknown"),
            resolution=str(raw.get("resolution") or raw.get("resolution_status") or "unknown"),
            resolution_text=str(raw.get("resolution_text") or raw.get("fix_note") or raw.get("resolution_note") or None),
            duplicate_of=raw.get("duplicate_of") or raw.get("duplicate") or None,
            created_at=raw.get("created_at") if isinstance(raw.get("created_at"), datetime) else None,
            resolved_at=raw.get("resolved_at") if isinstance(raw.get("resolved_at"), datetime) else None,
            source_url=raw.get("source_url") or raw.get("url") or None,
            has_stack_trace=bool(stack_trace),
        )
        defect.severity = str(raw.get("severity") or "unknown").lower() if raw.get("severity") else "unknown"
        defect.priority = str(raw.get("priority") or "unknown").lower() if raw.get("priority") else "unknown"
        defect.status = str(raw.get("status") or "unknown").lower() if raw.get("status") else "unknown"
        defect.resolution = str(raw.get("resolution") or "unknown").lower() if raw.get("resolution") else "unknown"
        defects.append(defect)
    return defects
