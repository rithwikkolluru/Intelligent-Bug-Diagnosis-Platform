from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


SCHEMA_VERSION = "2.0"


class BugSnapshot(BaseModel):
    """Immutable snapshot of the submitted bug fields (already redacted)."""
    bug_id: int
    title: str
    description: str
    stack_trace: str | None = None
    error_logs: str | None = None
    programming_language: str | None = None
    source_type: str = "paste"
    created_at: str  # ISO8601


class DerivedFacts(BaseModel):
    """Cross-agent derived fields pre-computed for downstream Milestone 3 agents.

    These fields are always present (may be None). Downstream agents MUST
    rely only on fields documented here, not on raw triage/log_analysis fields.
    """
    detected_language: str | None = Field(None, description="Reconciled from log analysis format + submission language")
    exception_type: str | None = Field(None, description="Simple exception name from log analysis")
    failure_point_summary: str | None = Field(None, description="'file:line in method' or best available from log analysis")
    component: str | None = Field(None, description="Canonical component name from triage")
    severity: str | None = Field(None, description="Critical|High|Medium|Low from triage")
    priority: str | None = Field(None, description="P1-P4 from triage")
    has_trace: bool = Field(False, description="Whether a parseable stack trace was found")
    triage_confidence: float | None = None
    log_analysis_confidence: float | None = None


class AgentRunRecord(BaseModel):
    """Lightweight per-agent execution record attached to BugContext."""
    agent_name: str
    status: str            # ok | skipped | partial | failed
    error_code: str | None = None
    duration_ms: float = 0.0
    provenance: dict[str, Any] = Field(default_factory=dict)


class BugContext(BaseModel):
    """
    The canonical output of the M2.3 analysis pipeline.
    Version: 2.0 — schema_version must be checked by any consumer before reading.

    Contract for Milestone 3 downstream agents:
    - 'bug' is ALWAYS present and fully populated.
    - 'derived' is ALWAYS present; individual fields may be None.
    - 'triage' is present iff triage ran (even if status is 'failed').
    - 'log_analysis' is present iff log analysis ran (or was skipped with reason).
    - 'analysis_status' is the definitive pipeline outcome.
    - Downstream agents MUST NOT re-derive facts that exist in 'derived'.
    """
    schema_version: str = SCHEMA_VERSION
    pipeline_version: str = "2.0.0"
    analysis_id: int | None = None
    bug: BugSnapshot
    triage: dict[str, Any] | None = None          # Serialised TriageResult or agent error
    log_analysis: dict[str, Any] | None = None    # Serialised LogAnalysisResult or agent error
    derived: DerivedFacts = Field(default_factory=DerivedFacts)
    analysis_status: str = "complete"             # complete | partial | failed
    agent_runs: list[AgentRunRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


def build_derived_facts(
    triage_result: Any | None,
    log_result: Any | None,
    submission_language: str | None,
) -> DerivedFacts:
    """Compute cross-agent DerivedFacts from agent outputs."""
    detected_lang = submission_language
    exception_type = None
    failure_point_summary = None
    component = None
    severity = None
    priority = None
    has_trace = False
    triage_conf = None
    log_conf = None

    if log_result is not None:
        log_conf = getattr(log_result, "confidence", None)
        fmt = getattr(log_result, "detected_format", None)
        if fmt and fmt not in ("unknown", "generic_log"):
            detected_lang = fmt
        exc = getattr(log_result, "exception_type", None)
        if exc:
            exception_type = getattr(exc, "simple_name", None) or getattr(exc, "fully_qualified", None)
        fp = getattr(log_result, "failure_point", None)
        if fp:
            has_trace = True
            parts = []
            if getattr(fp, "file", None):
                parts.append(fp.file)
            if getattr(fp, "line", None):
                parts[-1] = f"{parts[-1]}:{fp.line}" if parts else f":{fp.line}"
            if getattr(fp, "method", None):
                parts.append(f"in {fp.method}")
            failure_point_summary = " ".join(parts) if parts else None
        code_path = getattr(log_result, "code_path", None)
        if code_path and len(code_path) > 0:
            has_trace = True

    if triage_result is not None:
        triage_conf = getattr(triage_result, "confidence", None)
        comp = getattr(triage_result, "component", None)
        if comp:
            component = getattr(comp, "name", None)
        sev = getattr(triage_result, "severity", None)
        if sev:
            severity = sev.value if hasattr(sev, "value") else str(sev)
        prio = getattr(triage_result, "priority", None)
        if prio:
            priority = prio.value if hasattr(prio, "value") else str(prio)

    return DerivedFacts(
        detected_language=detected_lang,
        exception_type=exception_type,
        failure_point_summary=failure_point_summary,
        component=component,
        severity=severity,
        priority=priority,
        has_trace=has_trace,
        triage_confidence=triage_conf,
        log_analysis_confidence=log_conf,
    )
