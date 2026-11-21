# Agent Prompt Changelog

## v1.0.0 (2026-11-22) - Milestone 2 Baseline
- **Log Analysis Agent (v1):** Structured stack trace and log extractor with strict schema matching `LogAnalysisResult`. Instructs LLM to identify exception type, root error message, failure point, and execution code path. Guarded with untrusted data delimiters and prompt-injection defense.
- **Triage Agent (v1):** Defect classification prompt implementing 4-tier Severity (`Critical`, `High`, `Medium`, `Low`), Priority (`P1`, `P2`, `P3`, `P4`), and candidate Component matching. Embeds the official triage rubric. All few-shot examples are completely synthetic and exclude held-out evaluation pairs.
