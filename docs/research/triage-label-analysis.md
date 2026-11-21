# Triage Label Analysis & Classification Rubric Design

**Date:** 2026-11-22  
**Context:** Milestone 2.1 — Automated Triage Agent  
**Source Data:** `data/processed/defects.parquet` (standardised historical defect records from Mozilla, Apache, and Eclipse)

---

## 1. Dataset Verification & Distribution Analysis

### 1.1 Record Counts per Source
`data/processed/defects.parquet` contains **9 standardised defect records** across the 3 benchmark repositories:

| Project | Records | Share |
|---|---|---|
| **Mozilla** (Bugzilla) | 3 | 33.3% |
| **Eclipse** (Bugzilla) | 3 | 33.3% |
| **Apache** (Jira / Bugzilla) | 3 | 33.3% |
| **Total** | **9** | **100.0%** |

---

### 1.2 Severity Distribution per Project

| Project | Blocker | Critical | Major | Normal | Total |
|---|---|---|---|---|---|
| **Apache** | 1 (33.3%) | 1 (33.3%) | 1 (33.3%) | 0 (0.0%) | 3 |
| **Eclipse** | 0 (0.0%) | 0 (0.0%) | 2 (66.7%) | 1 (33.3%) | 3 |
| **Mozilla** | 0 (0.0%) | 1 (33.3%) | 1 (33.3%) | 1 (33.3%) | 3 |
| **Total** | **1 (11.1%)** | **2 (22.2%)** | **4 (44.4%)** | **2 (22.2%)** | **9** |

---

### 1.3 Priority Distribution per Project

| Project | P1 | P2 | P3 | Total |
|---|---|---|---|---|
| **Apache** | 1 (33.3%) | 2 (66.7%) | 0 (0.0%) | 3 |
| **Eclipse** | 1 (33.3%) | 2 (66.7%) | 0 (0.0%) | 3 |
| **Mozilla** | 2 (66.7%) | 0 (0.0%) | 1 (33.3%) | 3 |
| **Total** | **4 (44.4%)** | **4 (44.4%)** | **1 (11.1%)** | **9** |

---

### 1.4 Status & Resolution Distribution

| Project | Status: Fixed | Resolution: Fixed |
|---|---|---|
| **Apache** | 3 (100.0%) | 3 (100.0%) |
| **Eclipse** | 3 (100.0%) | 3 (100.0%) |
| **Mozilla** | 3 (100.0%) | 3 (100.0%) |
| **Total** | **9 (100.0%)** | **9 (100.0%)** |

All curated records represent verified, resolved production issues with verified patches and resolutions.

---

### 1.5 Component Analysis
There are **9 distinct components** across the 9 records (1 unique component per defect):

| Component | Project | Frequency | Sample Defect |
|---|---|---|---|
| `Core:DOM` | Mozilla | 1 | MOZ-12048 |
| `Network:Cache` | Mozilla | 1 | MOZ-88931 |
| `Layout:CSS` | Mozilla | 1 | MOZ-44129 |
| `JDT:Core` | Eclipse | 1 | ECLIPSE-9912 |
| `PyDev:Pipeline` | Eclipse | 1 | ECLIPSE-6541 |
| `Equinox:OSGi` | Eclipse | 1 | ECLIPSE-4421 |
| `Tomcat:Security` | Apache | 1 | APACHE-5120 |
| `Commons:Lang` | Apache | 1 | APACHE-3391 |
| `HttpComponents:Client` | Apache | 1 | APACHE-7890 |

---

### 1.6 Missing Data Share

| Field | Missing / Null Share | Empty String Share |
|---|---|---|
| `severity` | 0.0% (0 / 9) | 0.0% (0 / 9) |
| `priority` | 0.0% (0 / 9) | 0.0% (0 / 9) |
| `status` | 0.0% (0 / 9) | 0.0% (0 / 9) |
| `resolution` | 0.0% (0 / 9) | 0.0% (0 / 9) |
| `component` | 0.0% (0 / 9) | 0.0% (0 / 9) |
| `stack_trace` | 0.0% (0 / 9) | 0.0% (0 / 9) |

---

### 1.7 Severity vs. Priority Correlation

Cross-tabulation of Severity against Priority in `defects.parquet`:

| Severity \ Priority | P1 | P2 | P3 | Total |
|---|---|---|---|---|
| **Blocker** | 1 | 0 | 0 | 1 |
| **Critical** | 1 | 1 | 0 | 2 |
| **Major** | 2 | 2 | 0 | 4 |
| **Normal** | 0 | 1 | 1 | 2 |
| **Total** | **4** | **4** | **1** | **9** |

#### Key Observation on Severity vs. Priority:
Severity and Priority are correlated but **not identical**:
- **Critical & Blocker** defects map to P1 (release blocking / immediate crash), but a critical issue with an operational workaround can be triaged as P2.
- **Major** defects span both P1 and P2 depending on urgency (e.g. MOZ-12048 is Major + P1 because DOM event dispatch crashes affect core browser rendering; ECLIPSE-6541 is Major + P2 because pipeline KeyError has an ETL fallback).
- **Normal** defects span P2 and P3 depending on customer reach.

---

### 1.8 Class Imbalance in Defect Repositories & Accuracy Implications

In large real-world bug tracking databases (Bugzilla, Jira):
1. **The "Normal" Class Dominance:** Over 60–75% of raw Bugzilla reports are submitted with the default value `normal` (or `medium`). Similarly, `P3` is the standard default priority in Apache Jira and Bugzilla.
2. **Impact on Evaluation Metrics:**
   - **Accuracy is misleading:** A dummy classifier predicting `normal` or `Medium` for every bug report would achieve ~70% overall accuracy while failing on every severe crash, security leak, or blocker.
   - **Required Evaluation Metrics:** Milestone 2.4 evaluation harness must report **Macro-averaged F1**, **Balanced Accuracy**, and **Per-class Precision/Recall** (especially for Critical and High classes) rather than raw accuracy.
   - **Exclusions:** Native `enhancement`, `task`, and `unknown` values must be cleanly separated from defect triage evaluation.

---

## 2. Proposed Mappings & Rubric Design

Based on the empirical distribution and software defect engineering standards, we propose the following three unified specifications.

### Proposal A: Severity Mapping (4-Tier Unified Scale)

We standardize native Bugzilla and Jira severities to a 4-class taxonomy: **Critical**, **High**, **Medium**, **Low**.

| Unified Severity Class | Definition & Technical Impact | Native Values Mapped |
|---|---|---|
| **Critical** | System crash, unhandled kernel/runtime panic, data loss, memory corruption (SIGSEGV/double-free), severe security vulnerability (RCE/privilege escalation), complete blockage of core workflows with no workaround. | `blocker`, `critical`, `urgent` |
| **High** | Major functional breakdown, core service failure, severe memory/connection leak, unhandled NullPointerException / unhandled exceptions on primary user flows. Workaround is complex or degrades performance. | `major` |
| **Medium** | Moderate functional failure, non-critical feature broken, edge-case unhandled exception, performance regression, incorrect non-critical output. Reasonable workaround exists. | `normal`, `medium` |
| **Low** | Cosmetic glitch, UI alignment defect, typo, minor logging inconsistency, trivial edge case with negligible user impact. | `minor`, `trivial`, `low` |

#### Special Cases:
- `enhancement`, `feature_request`: Tagged as non-defect triage items; excluded from defect severity accuracy metrics.
- `unknown`, missing: Flags a warning `SEVERITY_UNKNOWN` and triggers inference via triage rules / LLM.

---

### Proposal B: Priority Scale (P1–P4) Defined by Impact AND Urgency

Priority measures **scheduling urgency** ($Impact \times Urgency$), whereas Severity measures **technical severity**. A critical defect with an easy workaround may be P2; a minor defect blocking a release deadline may be P1.

| Priority | Name | Impact + Urgency Criteria | Examples | Source Mapping |
|---|---|---|---|---|
| **P1** | **Urgent / Blocker** | Catastrophic impact OR release blocker. Active security exploitation, database corruption, production downtime affecting all users, regression in stable release. Requires immediate engineer assignment. | Double free in HTTP cache (MOZ-88931), Auth service crash under load (APACHE-5120). | `p1`, `highest`, `blocker` |
| **P2** | **High** | Significant business impact affecting a large user subset. Major workflow failing, but a manual or partial workaround exists. Must be resolved in the current sprint / next minor release. | ETL batch transformation crash on missing telemetry key (ECLIPSE-6541), CSV delimiter bounds exception (APACHE-3391). | `p2`, `high` |
| **P3** | **Medium** | Normal operational defect. Affects non-essential features, occasional edge cases, or has an established workaround. Scheduled in the normal backlog queue. | CSS parser error on empty rule set (MOZ-44129). | `p3`, `medium`, `normal` |
| **P4** | **Low** | Minimal urgency. Minor inconvenience, cosmetic flaw, documentation discrepancy, or obscure edge case. Scheduled when capacity allows. | Typo in error dialog, minor CSS padding mismatch. | `p4`, `p5`, `low`, `lowest` |

---

### Proposal C: Component Vocabulary Strategy

Bug report components vary dramatically between projects. A rigid global vocabulary causes high false-negative rates, while completely unconstrained text causes naming drift.

#### 3-Tier Hybrid Vocabulary Strategy:
1. **Curated Candidate Whitelist per Project:**
   - **Mozilla Candidates:** `Core:DOM`, `Network:Cache`, `Layout:CSS`, `Core:JavaScript`, `Security`, `Graphics`, `Firefox:General`
   - **Eclipse Candidates:** `JDT:Core`, `PyDev:Pipeline`, `Equinox:OSGi`, `Platform:UI`, `PDE:Core`, `CDT:Core`
   - **Apache Candidates:** `Tomcat:Security`, `Commons:Lang`, `HttpComponents:Client`, `Kafka:Core`, `Spark:Core`
2. **Context-Driven Normalization & Alias Mapping:**
   - Match package/namespace paths extracted by the Log Analysis Agent:
     - `org.apache.catalina.*` -> `Tomcat:Security` / `Tomcat:Core`
     - `org.eclipse.jdt.*` -> `JDT:Core`
     - `org.apache.commons.lang*` / `commons.text*` -> `Commons:Lang`
     - `dom.js` / `dispatchEvent` -> `Core:DOM`
     - `CacheBuffer` / socket -> `Network:Cache`
3. **Graceful Open Vocabulary Fallback:**
   - If the project is unknown or the extracted component does not match the project candidate list:
     - The agent returns the inferred functional module (e.g. `Authentication`, `DatabasePool`, `UI:Components`).
     - Sets `matched_vocabulary: false`.
     - Flags `COMPONENT_UNMATCHED_VOCABULARY` in warnings.
   - If no component can be identified, returns `"unknown"` with low confidence.
