# Defect Triage Rubric

This document defines the official classification rubric for software defect triage in the Intelligent Bug Diagnosis Platform.

---

## 1. Technical Severity (Impact Scale)

Severity assesses the inherent technical damage, failure mode, and system stability impact.

| Severity | Technical Definition | Examples & Key Indicators |
|---|---|---|
| **Critical** | System crash, process termination, kernel panic, unrecoverable data loss, database corruption, severe security vulnerability (RCE, privilege escalation, auth bypass), core functionality completely unusable with zero workaround. | `SIGSEGV`, `SIGBUS`, `OutOfMemoryError`, `double free`, database corruption, unhandled system deadlock. |
| **High** | Major functional failure, primary feature broken, severe memory/connection pool leak, socket exhaustion, unhandled exceptions in critical business paths. A workaround exists but is complex or manual. | `NullPointerException` in main flow, HTTP 500 on checkout/auth, memory leak causing degraded throughput. |
| **Medium** | Moderate functional failure, edge case defect, non-critical feature degradation, minor race condition. Reasonable, accessible workaround is available. | Form validation bug on non-mandatory field, export to CSV missing a header, UI rendering delay on slow connections. |
| **Low** | Cosmetic flaws, UI alignment errors, typography errors, minor console logging noise, documentation typos. Negligible impact on user capability. | Misaligned button, typo in settings tooltip, warning log on clean shutdown. |

---

## 2. Priority Scale (Urgency & Business Impact)

Priority answers *when* and *in what order* the defect must be fixed, combining technical impact with user reach and business risk.

| Priority | Definition | Target Resolution Window |
|---|---|---|
| **P1** | Blocker / Outage: Active production outage, release blocker, critical security exploit, or severe data loss. Immediate intervention required. | Immediate hotfix / within 24 hours. |
| **P2** | Major Issue: Critical or High severity bug affecting a significant portion of users in standard workflows, or high-priority regression. | Current sprint / next scheduled release. |
| **P3** | Normal / Backlog: Standard bug with available workaround or impacting edge scenarios. | Standard backlog prioritization. |
| **P4** | Low / Nice-to-Have: Cosmetic defect, minor inconvenience, or polish request. | Capacity-dependent backlog. |

---

## 3. Component Vocabulary Strategy

Components are identified following a 3-tier hierarchy:
1. **Tier 1 (Project Canonical Vocabulary):** Match against known project subsystems (e.g. `Tomcat:Catalina`, `Core:DOM`, `JDT:Core`).
2. **Tier 2 (Code Namespace Inference):** Direct mapping from stack trace package names (e.g., `org.apache.catalina` $\rightarrow$ `Tomcat:Catalina`).
3. **Tier 3 (General Fallback):** Flagged as `matched_vocabulary: false` with top-3 closest candidates provided.
