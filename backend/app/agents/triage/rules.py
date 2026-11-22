from __future__ import annotations

import re

from app.agents.base import AgentInput
from app.agents.triage.schemas import (
    ComponentInfo,
    ConfidenceBreakdown,
    Priority,
    Severity,
    TriageResult,
)
from app.agents.triage.vocabulary import match_component

CRITICAL_SIGNALS = [
    r"\b(sigsegv|sigbus|segmentation fault|core dump|kernel panic)\b",
    r"\b(data loss|corrupt(?:ion|ed)|database corruption|unrecoverable)\b",
    r"\b(remote code execution|rce|privilege escalation|cve-\d{4}-\d+|vulnerability)\b",
    r"\b(deadlock|freeze|system crash|out of memory|outofmemoryerror)\b",
]

HIGH_SIGNALS = [
    r"\b(nullpointerexception|null pointer dereference|uncaught exception)\b",
    r"\b(connection refused|timeout|socket timeout|connection pool exhausted)\b",
    r"\b(service down|feature unavailable|cannot login|authentication failed)\b",
    r"\b(memory leak|leak|thread leak|infinite loop|stack overflow)\b",
]

LOW_SIGNALS = [
    r"\b(typo|misspelling|cosmetic|css|padding|color|alignment|margin)\b",
    r"\b(ui glitch|button icon|minor visual|tooltip)\b",
    r"\b(documentation|readme|comment typo)\b",
]

URGENCY_P1_SIGNALS = [
    r"\b(production outage|prod down|release blocker|blocker|data corruption)\b",
    r"\b(security exploit|active exploit|immediate hotfix)\b",
]

URGENCY_P2_SIGNALS = [
    r"\b(regression|broken in latest|sprint blocker|major impact)\b",
    r"\b(many users affected|customer escalation)\b",
]

URGENCY_P4_SIGNALS = [
    r"\b(minor|cosmetic|typo|nice to have|low priority|enhancement)\b",
]


def evaluate_rule_baseline(bug_input: AgentInput) -> TriageResult:
    """Deterministic, fast heuristic baseline for bug triage."""
    text = f"{bug_input.title} {bug_input.description}".lower()
    trace_and_logs = f"{bug_input.stack_trace or ''} {bug_input.error_logs or ''}".lower()
    combined_content = f"{text} {trace_and_logs}"

    signals_found: list[str] = []
    evidence_quotes: list[str] = []

    # 1. Assess Severity
    sev = Severity.MEDIUM
    sev_conf = 0.65

    # Check Critical
    for pattern in CRITICAL_SIGNALS:
        m = re.search(pattern, combined_content, re.IGNORECASE)
        if m:
            sev = Severity.CRITICAL
            sev_conf = 0.90
            signals_found.append(f"severity:{m.group(0)}")
            evidence_quotes.append(m.group(0))
            break

    # Check High if not Critical
    if sev == Severity.MEDIUM:
        for pattern in HIGH_SIGNALS:
            m = re.search(pattern, combined_content, re.IGNORECASE)
            if m:
                sev = Severity.HIGH
                sev_conf = 0.85
                signals_found.append(f"severity:{m.group(0)}")
                evidence_quotes.append(m.group(0))
                break

    # Check Low
    if sev == Severity.MEDIUM:
        for pattern in LOW_SIGNALS:
            m = re.search(pattern, combined_content, re.IGNORECASE)
            if m:
                sev = Severity.LOW
                sev_conf = 0.80
                signals_found.append(f"severity:{m.group(0)}")
                evidence_quotes.append(m.group(0))
                break

    # 2. Assess Priority (combining severity with urgency signals)
    prio = Priority.P3
    prio_conf = 0.65

    p1_match = any(re.search(p, combined_content, re.IGNORECASE) for p in URGENCY_P1_SIGNALS)
    p2_match = any(re.search(p, combined_content, re.IGNORECASE) for p in URGENCY_P2_SIGNALS)
    p4_match = any(re.search(p, combined_content, re.IGNORECASE) for p in URGENCY_P4_SIGNALS)

    if sev == Severity.CRITICAL or p1_match:
        prio = Priority.P1
        prio_conf = 0.90
        signals_found.append("priority:P1_outage_or_critical")
    elif sev == Severity.HIGH or p2_match:
        prio = Priority.P2
        prio_conf = 0.80
        signals_found.append("priority:P2_high_impact_or_regression")
    elif sev == Severity.LOW or p4_match:
        prio = Priority.P4
        prio_conf = 0.85
        signals_found.append("priority:P4_minor_or_cosmetic")
    else:
        prio = Priority.P3
        prio_conf = 0.70

    # 3. Assess Component
    comp_name, matched, alts = match_component(
        text=f"{bug_input.title} {bug_input.description}",
        trace_text=f"{bug_input.stack_trace or ''} {bug_input.error_logs or ''}",
    )
    comp_conf = 0.85 if matched else 0.40
    if matched:
        signals_found.append(f"component:{comp_name}")

    overall_conf = round((sev_conf * 0.4) + (prio_conf * 0.4) + (comp_conf * 0.2), 2)

    reasoning = (
        f"Rule-based classification: Assigned {sev.value} severity and {prio.value} priority "
        f"based on signals: {', '.join(signals_found) if signals_found else 'standard defect indicators'}. "
        f"Component '{comp_name}' was {'matched from vocabulary/trace' if matched else 'inferred as general'}"
    )

    warnings: list[str] = []
    if not matched:
        warnings.append("Component not found in known project vocabulary")
    if not bug_input.description and not bug_input.stack_trace:
        warnings.append("Sparse input: title only provided")

    return TriageResult(
        severity=sev,
        priority=prio,
        component=ComponentInfo(name=comp_name, matched_vocabulary=matched, alternatives=alts),
        confidence=overall_conf,
        confidence_breakdown=ConfidenceBreakdown(
            severity=sev_conf,
            priority=prio_conf,
            component=comp_conf,
        ),
        reasoning=reasoning,
        evidence_quotes=evidence_quotes[:5],
        signals_used=signals_found,
        warnings=warnings,
    )
