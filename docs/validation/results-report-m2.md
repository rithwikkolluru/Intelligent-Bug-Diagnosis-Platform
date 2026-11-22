# Milestone 2: Agent Accuracy Validation & Evaluation Report

**Date:** 2026-11-22  
**Pipeline Version:** 2.0.0  
**Evaluation Scope:** M2.1 Triage Agent, M2.2 Log Analysis Agent, M2.4 Validation Test Set

---

## 1. Executive Summary

| Agent / Metric | Total Evaluated | Correct / Extracted | Accuracy Rate |
|---|---|---|---|
| **Triage: Severity** | 9 | 3 | **33.3%** |
| **Triage: Priority** | 9 | 2 | **22.2%** |
| **Triage: Component Match** | 9 | 2 | **22.2%** |
| **Log: Format Detection** | 10 | 10 | **100.0%** |
| **Log: Exception Extraction** | 10 | 10 | **100.0%** |
| **Log: Failure Point (file+line)** | 10 | 10 | **100.0%** |
| **Log: Code Path Extraction** | 10 | 9 | **90.0%** |

---

## 2. Input Formats & Coverage Tested

The evaluation harness verified agent behavior across all required input combinations:

- [x] **Descriptions only**: Triage classifies severity/priority; log analysis cleanly skips with `NO_LOG_CONTENT`.
- [x] **Descriptions with stack traces**: Both agents trigger and extract rich context.
- [x] **Logs without descriptions**: Log analysis parses traces; triage falls back to trace heuristics.
- [x] **Messy / unstructured logs**: Robust fallback to `generic_log` without crashing.

---

## 3. Triage Agent Breakdown (Historical Seeded Dataset)

| Defect ID | Project | Expected Severity | Predicted | Expected Priority | Predicted | Component | Confidence |
|---|---|---|---|---|---|---|---|
| `mozilla-MOZ-12048` | mozilla | High | Medium | P1 | P3 | Core:DOM | 0.71 |
| `mozilla-MOZ-88931` | mozilla | Critical | Critical | P1 | P1 | General:Unknown | 0.80 |
| `mozilla-MOZ-44129` | mozilla | Medium | High | P3 | P2 | General:Unknown | 0.74 |
| `eclipse-ECLIPSE-9912` | eclipse | High | High | P1 | P2 | Platform:Core | 0.83 |
| `eclipse-ECLIPSE-6541` | eclipse | High | Medium | P2 | P3 | General:Unknown | 0.62 |
| `eclipse-ECLIPSE-4421` | eclipse | Medium | Medium | P2 | P3 | General:Unknown | 0.62 |
| `apache-APACHE-5120` | apache | Critical | High | P1 | P2 | General:Unknown | 0.74 |
| `apache-APACHE-3391` | apache | High | Medium | P2 | P3 | General:Unknown | 0.62 |
| `apache-APACHE-7890` | apache | Critical | High | P2 | P2 | General:Unknown | 0.74 |

---

## 4. Log Analysis Agent Breakdown (Multi-Format Fixtures)

| Fixture | Expected Format | Detected Format | Exception Match | Failure Point Match | Frames | Confidence |
|---|---|---|---|---|---|---|
| `android_logcat.log` | android_logcat | android_logcat | ✅ | ✅ | 2 | 1.00 |
| `cpp_gdb.log` | cpp_gdb | cpp_gdb | ✅ | ✅ | 4 | 1.00 |
| `dotnet.log` | dotnet | dotnet | ✅ | ✅ | 2 | 1.00 |
| `generic_error.log` | generic_log | generic_log | ✅ | ✅ | 0 | 0.25 |
| `go_panic.log` | go | go | ✅ | ✅ | 2 | 1.00 |
| `html_escaped.log` | java | java | ✅ | ✅ | 2 | 1.00 |
| `java_npe.log` | java | java | ✅ | ✅ | 4 | 1.00 |
| `javascript_firefox.log` | javascript_firefox | javascript_firefox | ✅ | ✅ | 3 | 1.00 |
| `javascript_v8.log` | javascript_v8 | javascript_v8 | ✅ | ✅ | 3 | 1.00 |
| `python_keyerror.log` | python | python | ✅ | ✅ | 1 | 0.90 |

---

## 5. Failure Case Analysis & Improvements

### Failure Cases Observed:
- **Triage Mismatch on `mozilla-MOZ-12048`**: Sev expected High vs Medium; Reason: Rule-based classification: Assigned Medium severity and P3 priority based on signals: component:Core:DOM. Component 'Core:DOM' was matched from vocabulary/trace
- **Triage Mismatch on `mozilla-MOZ-88931`**: Sev expected Critical vs Critical; Reason: Rule-based classification: Assigned Critical severity and P1 priority based on signals: severity:sigsegv, priority:P1_outage_or_critical. Component 'General:Unknown' was inferred as general
- **Triage Mismatch on `mozilla-MOZ-44129`**: Sev expected Medium vs High; Reason: Rule-based classification: Assigned High severity and P2 priority based on signals: severity:null pointer dereference, priority:P2_high_impact_or_regression. Component 'General:Unknown' was inferred as general
- **Triage Mismatch on `eclipse-ECLIPSE-9912`**: Sev expected High vs High; Reason: Rule-based classification: Assigned High severity and P2 priority based on signals: severity:nullpointerexception, priority:P2_high_impact_or_regression, component:Platform:Core. Component 'Platform:Core' was matched from vocabulary/trace
- **Triage Mismatch on `eclipse-ECLIPSE-6541`**: Sev expected High vs Medium; Reason: Rule-based classification: Assigned Medium severity and P3 priority based on signals: standard defect indicators. Component 'General:Unknown' was inferred as general
- **Triage Mismatch on `eclipse-ECLIPSE-4421`**: Sev expected Medium vs Medium; Reason: Rule-based classification: Assigned Medium severity and P3 priority based on signals: standard defect indicators. Component 'General:Unknown' was inferred as general
- **Triage Mismatch on `apache-APACHE-5120`**: Sev expected Critical vs High; Reason: Rule-based classification: Assigned High severity and P2 priority based on signals: severity:nullpointerexception, priority:P2_high_impact_or_regression. Component 'General:Unknown' was inferred as general
- **Triage Mismatch on `apache-APACHE-3391`**: Sev expected High vs Medium; Reason: Rule-based classification: Assigned Medium severity and P3 priority based on signals: standard defect indicators. Component 'General:Unknown' was inferred as general
- **Triage Mismatch on `apache-APACHE-7890`**: Sev expected Critical vs High; Reason: Rule-based classification: Assigned High severity and P2 priority based on signals: severity:timeout, priority:P2_high_impact_or_regression. Component 'General:Unknown' was inferred as general

### Applied Fixes & Mitigations:
1. **JavaScript V8 Anonymous/Eval frame handling**: Added dedicated regex to extract the inner file from `eval at ...` wrapper frames.
2. **Component Vocabulary Boundary cutoffs**: Raised fuzzy similarity cutoffs to 0.92 to prevent false-positive matches on common English words.
3. **Dual Execution Fallback**: LLM parsing errors automatically fall back to the deterministic rule baseline, ensuring zero hard crashes.