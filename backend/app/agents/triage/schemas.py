from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class ComponentInfo(BaseModel):
    name: str = Field(..., description="Canonical or identified component name")
    matched_vocabulary: bool = Field(False, description="Whether name matched the known project vocabulary")
    alternatives: list[str] = Field(default_factory=list, description="Top-k alternative candidate components")


class ConfidenceBreakdown(BaseModel):
    severity: float = Field(0.0, ge=0.0, le=1.0)
    priority: float = Field(0.0, ge=0.0, le=1.0)
    component: float = Field(0.0, ge=0.0, le=1.0)


class TriageResult(BaseModel):
    severity: Severity = Field(..., description="Technical impact classification")
    priority: Priority = Field(..., description="Urgency and business impact prioritization")
    component: ComponentInfo = Field(..., description="Identified subsystem or module")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall triage confidence")
    confidence_breakdown: ConfidenceBreakdown = Field(..., description="Individual confidence scores")
    reasoning: str = Field(..., description="Concise rationale explaining the assignment")
    evidence_quotes: list[str] = Field(default_factory=list, description="Direct supporting quotes from text/trace")
    signals_used: list[str] = Field(default_factory=list, description="Key heuristic or semantic signals triggered")
    warnings: list[str] = Field(default_factory=list, description="Warnings such as low vocabulary match or truncated input")
