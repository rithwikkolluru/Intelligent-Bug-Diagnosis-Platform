# Database Schema

## Implemented entities

### BugReport (implemented)

| Field | Type | Notes |
| --- | --- | --- |
| bug_id | int PK | Auto-incrementing identifier |
| title | str | Required, max 300 chars |
| description | text | Required |
| stack_trace | text | Optional |
| error_logs | text | Optional |
| programming_language | str | Optional |
| source_type | str | paste or upload |
| original_filename | str | Optional |
| status | str | Default: received |
| redaction_count | int | Count of secret redactions |
| created_at | datetime | UTC timestamp |

### HistoricalDefect (implemented in the RAG layer)

| Field | Type | Notes |
| --- | --- | --- |
| defect_id | str | Globally unique id of the form `<project>-<original_id>` |
| original_id | str | Raw source identifier |
| project | str | `mozilla`, `apache` or `eclipse` |
| component | str | Optional component name |
| summary | str | Short title or summary |
| description | str | Full textual description |
| stack_trace | str | Nullable raw stack trace |
| comments | list[dict] | Ordered comment payloads |
| severity | str | Normalised vocabulary, `unknown` if not mapped |
| priority | str | Normalised vocabulary, `unknown` if not mapped |
| status | str | Normalised vocabulary, `unknown` if not mapped |
| resolution | str | Normalised resolution state |
| resolution_text | str | Optional fix note or resolution text |
| duplicate_of | str | Master defect id referenced by a duplicate |
| created_at | datetime | Optional created timestamp |
| resolved_at | datetime | Optional resolved timestamp |
| source_url | str | Optional source URL |
| has_stack_trace | bool | Whether a trace is present |

### BugChunk (implemented in the RAG layer)

| Field | Type | Notes |
| --- | --- | --- |
| chunk_id | str | Unique deterministic id |
| defect_id | str | Parent defect id |
| chunk_type | str | `description`, `stack_trace`, `comment`, `resolution` |
| text | str | Embeddable chunk content |
| token_count | int | Approximate token count |
| metadata | dict | ChromaDB-compatible metadata values only |

### ChromaDB metadata schema

The vector store metadata is intentionally restricted to scalar values:

- `project` (str)
- `component` (str)
- `severity` (str)
- `priority` (str)
- `status` (str)
- `resolution` (str)
- `has_stack_trace` (bool)
- `source_url` (str)
- `created_year` (int)
