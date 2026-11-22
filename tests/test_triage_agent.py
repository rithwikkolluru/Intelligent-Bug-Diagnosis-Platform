from __future__ import annotations

import pytest

from app.agents.base import AgentInput
from app.agents.triage.agent import TriageAgent
from app.agents.triage.rules import evaluate_rule_baseline
from app.agents.triage.schemas import (
    ComponentInfo,
    ConfidenceBreakdown,
    Priority,
    Severity,
    TriageResult,
)
from app.agents.triage.vocabulary import (
    match_component,
    normalize_component_name,
)
from app.llm.client import FakeLLMClient


# ---------------------------------------------------------
# 1. Schemas & Enums
# ---------------------------------------------------------
def test_triage_schemas_and_enums():
    res = TriageResult(
        severity=Severity.CRITICAL,
        priority=Priority.P1,
        component=ComponentInfo(name="Core:DOM", matched_vocabulary=True, alternatives=["Core:Layout"]),
        confidence=0.92,
        confidence_breakdown=ConfidenceBreakdown(severity=0.95, priority=0.92, component=0.90),
        reasoning="Critical browser crash in DOM tree parser.",
        evidence_quotes=["SIGSEGV in nsDOMParser"],
        signals_used=["sigsegv", "crash"],
        warnings=[],
    )
    assert res.severity == Severity.CRITICAL
    assert res.priority == Priority.P1
    assert res.component.name == "Core:DOM"
    assert res.confidence == 0.92
    assert "SIGSEGV in nsDOMParser" in res.evidence_quotes


def test_triage_invalid_severity():
    with pytest.raises(ValueError):
        TriageResult(
            severity="Blocker",  # invalid enum
            priority=Priority.P1,
            component=ComponentInfo(name="Core"),
            confidence=0.8,
            confidence_breakdown=ConfidenceBreakdown(severity=0.8, priority=0.8, component=0.8),
            reasoning="test",
        )


# ---------------------------------------------------------
# 2. Vocabulary & Normalization
# ---------------------------------------------------------
def test_component_normalization():
    assert normalize_component_name("  Core::DOM  ") == "Core:DOM"
    assert normalize_component_name("Platform/UI") == "Platform:UI"
    assert normalize_component_name("") == "Unknown"


def test_match_component_from_trace_packages():
    trace = "at org.apache.catalina.core.StandardContext.start(StandardContext.java:120)"
    comp, matched, alts = match_component(text="", trace_text=trace)
    assert matched is True
    assert comp == "Tomcat:Catalina"


def test_match_component_from_text_mention():
    text = "Error occurred while rendering layout in the browser"
    comp, matched, alts = match_component(text=text, project="mozilla")
    assert matched is True
    assert comp == "Core:Layout"


def test_match_component_unknown_fallback():
    comp, matched, alts = match_component(text="some random unindexed gizmo feature")
    assert matched is False
    assert comp == "General:Unknown"
    assert len(alts) > 0


# ---------------------------------------------------------
# 3. Rule Baseline Evaluation
# ---------------------------------------------------------
def test_rule_baseline_critical_crash():
    bug = AgentInput(
        title="Worker process terminated with SIGSEGV in memory allocator",
        description="Segmentation fault core dumped during high load test",
    )
    res = evaluate_rule_baseline(bug)
    assert res.severity == Severity.CRITICAL
    assert res.priority == Priority.P1
    assert "sigsegv" in res.signals_used[0].lower()


def test_rule_baseline_high_nullpointer():
    bug = AgentInput(
        title="Unhandled NullPointerException when loading dashboard",
        description="User cannot see widgets. Workaround: refresh page twice.",
        stack_trace="java.lang.NullPointerException\n  at com.app.Widget.render(Widget.java:45)",
    )
    res = evaluate_rule_baseline(bug)
    assert res.severity == Severity.HIGH
    assert res.priority in (Priority.P2, Priority.P3)


def test_rule_baseline_low_cosmetic():
    bug = AgentInput(
        title="Typo in settings header tooltip and minor css alignment padding",
        description="The word 'Configuration' is misspelled as 'Configuraton'.",
    )
    res = evaluate_rule_baseline(bug)
    assert res.severity == Severity.LOW
    assert res.priority == Priority.P4


def test_rule_baseline_p1_outage_signal():
    bug = AgentInput(
        title="Production outage: authentication service down",
        description="Active exploit causing auth service to fail for all users. Immediate hotfix required.",
    )
    res = evaluate_rule_baseline(bug)
    assert res.priority == Priority.P1


# ---------------------------------------------------------
# 4. Triage Agent Integration & LLM
# ---------------------------------------------------------
def test_triage_agent_rule_fallback_when_no_llm():
    agent = TriageAgent(llm_client=None)
    bug = AgentInput(
        title="Database deadlock in order processing",
        description="Deadlock detected during concurrent checkout transactions.",
    )
    result = agent.run(bug)
    assert result.status == "ok"
    assert result.provenance["method"] == "rule"
    assert result.output is not None
    assert result.output.severity == Severity.CRITICAL


def test_triage_agent_with_fake_llm():
    fake_client = FakeLLMClient(
        canned_responses=[
            {
                "severity": "High",
                "priority": "P2",
                "component": {"name": "Core:DOM", "matched_vocabulary": True, "alternatives": []},
                "confidence": 0.88,
                "confidence_breakdown": {"severity": 0.90, "priority": 0.85, "component": 0.90},
                "reasoning": "Major DOM event bubbling defect affecting primary interactions.",
                "evidence_quotes": ["DOM event fails to bubble"],
                "signals_used": ["dom", "event-failure"],
                "warnings": [],
            }
        ]
    )
    agent = TriageAgent(llm_client=fake_client)
    bug = AgentInput(
        title="DOM event fails to bubble to parent node in Firefox",
        description="Click events do not reach enclosing container.",
    )
    res = agent.run(bug)
    assert res.status == "ok"
    assert res.provenance["method"] in ("llm", "hybrid")
    assert res.output is not None
    assert res.output.severity == Severity.HIGH
    assert res.output.priority == Priority.P2
    assert res.output.component.name == "Core:DOM"


def test_triage_agent_graceful_recovery_on_llm_error():
    fake_client = FakeLLMClient(canned_responses=[RuntimeError("API quota exhausted")])
    agent = TriageAgent(llm_client=fake_client)
    bug = AgentInput(
        title="SIGSEGV crash in Core:Graphics rendering pipeline",
        description="Browser crashes immediately when opening WebGL test page.",
    )
    res = agent.run(bug)
    # Never raises; falls back to rule baseline with status ok
    assert res.status == "ok"
    assert res.provenance["method"] == "rule"
    assert res.output is not None
    assert res.output.severity == Severity.CRITICAL
    assert any("LLM triage failed" in w for w in res.warnings)


def test_triage_agent_secret_redaction_safety_net():
    fake_client = FakeLLMClient(
        canned_responses=[
            {
                "severity": "Medium",
                "priority": "P3",
                "component": {"name": "General:Unknown", "matched_vocabulary": False, "alternatives": []},
                "confidence": 0.70,
                "confidence_breakdown": {"severity": 0.7, "priority": 0.7, "component": 0.7},
                "reasoning": "Safe triage.",
                "evidence_quotes": [],
                "signals_used": [],
                "warnings": [],
            }
        ]
    )
    agent = TriageAgent(llm_client=fake_client)
    bug = AgentInput(
        title="Config error with token",
        description="Failure with token: ghp_123456789012345678901234567890123456 in header.",
    )
    res = agent.run(bug)
    assert res.status == "ok"
    # Check that secret was caught and recorded
    assert any("REDACTED" in w.upper() for w in res.warnings)
    # Check that call record in fake client does not contain raw secret
    call_content = fake_client.calls[0]["user_content"]
    assert "ghp_123456789012345678901234567890123456" not in call_content
    assert "[REDACTED" in call_content
