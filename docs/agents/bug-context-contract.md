# Bug Context Contract — Milestone 2.3

**Schema Version:** `2.0`  
**Pipeline Version:** `2.0.0`  
**Owner:** Orchestration layer (`app/orchestration/graph.py`)  
**Last updated:** 2026-11-22

---

## Overview

`BugContext` is the canonical output of the M2.3 analysis pipeline. It is a versioned, JSON-serialisable document produced after every analysis run and stored in the `bug_analyses` table. Downstream Milestone 3 agents (Duplicate Detection, Root Cause, Remediation) MUST read only the fields documented here and MUST check `schema_version == "2.0"` before reading any field.

The schema is defined in `backend/app/schemas/bug_context.py`.

---

## Top-Level Fields

| Field | Type | Always present? | Owner | Description |
|---|---|---|---|---|
| `schema_version` | `str` | ✅ Yes | Static | Currently `"2.0"`. Bump on breaking changes. |
| `pipeline_version` | `str` | ✅ Yes | Config | From `PIPELINE_VERSION` env var, e.g. `"2.0.0"`. |
| `analysis_id` | `int \| null` | Nullable | Orchestrator | DB primary key of this analysis attempt. `null` if run outside DB. |
| `bug` | `BugSnapshot` | ✅ Yes | Bug Submission Module | Immutable snapshot of the submitted bug. |
| `triage` | `dict \| null` | Nullable | Triage Agent | Serialised `TriageResult`. `null` if triage skipped or failed before producing any output. |
| `log_analysis` | `dict \| null` | Nullable | Log Analysis Agent | Serialised `LogAnalysisResult`. `null` if no log content or agent failed. |
| `derived` | `DerivedFacts` | ✅ Yes | Orchestrator | Pre-computed cross-agent facts. Individual sub-fields may be `null`. |
| `analysis_status` | `str` | ✅ Yes | Orchestrator | `"complete"` \| `"partial"` \| `"failed"` |
| `agent_runs` | `list[AgentRunRecord]` | ✅ Yes | Orchestrator | Per-agent execution records (may be empty on graph abort). |
| `warnings` | `list[str]` | ✅ Yes | Merged | Non-fatal warnings from all agents, deduplicated. |
| `errors` | `list[dict]` | ✅ Yes | Merged | Typed error dicts with `code` and `message` keys. |
| `created_at` | `str` (ISO8601) | ✅ Yes | Static | UTC timestamp when this context was built. |

---

## BugSnapshot

Immutable copy of the bug as stored (all secrets already redacted by the submission module).

| Field | Type | Nullable | Description |
|---|---|---|---|
| `bug_id` | `int` | No | DB primary key |
| `title` | `str` | No | Bug title |
| `description` | `str` | No | Full description |
| `stack_trace` | `str` | Yes | Raw stack trace text if provided |
| `error_logs` | `str` | Yes | Raw error log text if provided |
| `programming_language` | `str` | Yes | User-specified language |
| `source_type` | `str` | No | `"paste"` or `"upload"` |
| `created_at` | `str` | No | ISO8601 UTC creation time |

---

## DerivedFacts

Pre-computed by the orchestrator from triage + log analysis outputs. These fields exist for convenience: downstream agents MUST NOT re-derive anything that is here.

| Field | Type | Nullable | Source | Description |
|---|---|---|---|---|
| `detected_language` | `str` | Yes | Log Analysis → Submission | Reconciled language. Log analysis format detection takes priority; falls back to submission `programming_language`. |
| `exception_type` | `str` | Yes | Log Analysis | Simple exception/error class name (e.g. `"NullPointerException"`). |
| `failure_point_summary` | `str` | Yes | Log Analysis | Human-readable `"file:line in method"` string from failure point. |
| `component` | `str` | Yes | Triage | Canonical component name from triage vocabulary. |
| `severity` | `str` | Yes | Triage | `Critical` \| `High` \| `Medium` \| `Low` |
| `priority` | `str` | Yes | Triage | `P1` \| `P2` \| `P3` \| `P4` |
| `has_trace` | `bool` | No (default `false`) | Log Analysis | `true` if a parseable stack trace or non-empty code path was found. |
| `triage_confidence` | `float` | Yes | Triage | 0.0–1.0 confidence from triage agent. |
| `log_analysis_confidence` | `float` | Yes | Log Analysis | 0.0–1.0 confidence from log analysis agent. |

---

## AgentRunRecord

One record per agent that was invoked (or skipped). Downstream agents use this for provenance.

| Field | Type | Nullable | Description |
|---|---|---|---|
| `agent_name` | `str` | No | `"triage"` or `"log_analysis"` |
| `status` | `str` | No | `"ok"` \| `"partial"` \| `"skipped"` \| `"failed"` |
| `error_code` | `str` | Yes | Machine-readable error code (see table below) |
| `duration_ms` | `float` | No | Wall-clock time in milliseconds |
| `provenance` | `dict` | No | `{method, provider, model, prompt_version, cache_hit}` |

### Error Codes

| Code | Meaning |
|---|---|
| `INVALID_INPUT` | Bug report had no meaningful content (empty title, description, trace, logs). |
| `AGENT_FAILED` | Agent raised an unexpected exception. |
| `NO_LOG_CONTENT` | Log analysis skipped because no stack trace or error logs were provided. |
| `LLM_UNAVAILABLE` | LLM provider not configured or unreachable; fell back to rules. |
| `ANALYSIS_ABORTED` | Graph invocation itself failed completely. |

---

## `analysis_status` Semantics

| Value | Meaning | Downstream guidance |
|---|---|---|
| `"complete"` | Both triage AND log analysis completed successfully (ok or partial). Log analysis may be `"skipped"` with reason `NO_LOG_CONTENT` and still count as complete. | Full trust in `derived` fields. |
| `"partial"` | At least one agent succeeded; at least one failed or produced no output. | Use present fields; treat absent `derived` sub-fields as unknown. |
| `"failed"` | No agent produced usable output. Triggered by `INVALID_INPUT` or complete graph abort. | Do not attempt downstream analysis on this context. |

---

## Downstream Agent Rules (Milestone 3 Contract)

1. **Always check `schema_version == "2.0"`** before reading any field.
2. **Use `derived.*` fields** as the authoritative source for language, exception type, failure point, component, severity, and priority. Do not re-parse `triage` or `log_analysis` dicts directly.
3. **Treat `null` derived fields as unknown**, not as "not applicable". Do not short-circuit on them.
4. **Check `analysis_status`** before consuming any agent outputs. If `"failed"`, emit a diagnostic and skip agent-specific processing.
5. **`bug.description` and `bug.stack_trace` are always safe to read** (redaction is guaranteed by the submission module).
6. **Do not modify `BugContext`** — it is an immutable read-only contract. Downstream agents produce their own output schemas.
7. **`agent_runs` provenance is informational** — do not branch on `method` values (`"rule"`, `"llm"`, `"hybrid"`) for correctness; only use them for logging.

---

## Versioning Policy

- Minor additions (new nullable fields in `DerivedFacts` or `AgentRunRecord`) → increment `schema_version` minor digit, e.g. `"2.1"`.
- Breaking field renames or removals → increment major digit to `"3.0"` and update this document.
- `pipeline_version` tracks orchestration code changes independent of schema version.
- Stored contexts in the database carry their `schema_version` and are forward-read-compatible with the same major version.
