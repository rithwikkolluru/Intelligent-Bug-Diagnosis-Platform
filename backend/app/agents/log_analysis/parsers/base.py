from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from app.agents.log_analysis.schemas import (
    ConfidenceBreakdown,
    ExceptionChainItem,
    ExceptionInfo,
    FailurePoint,
    Frame,
)


class ParserOutput(BaseModel):
    """Intermediate extraction result produced by a deterministic language parser."""

    detected_format: str
    exception_type: ExceptionInfo = Field(default_factory=ExceptionInfo)
    error_message: str = ""
    failure_point: FailurePoint | None = None
    frames: list[Frame] = Field(default_factory=list)
    exception_chain: list[ExceptionChainItem] = Field(default_factory=list)
    root_cause_exception: ExceptionChainItem | None = None
    confidence_breakdown: ConfidenceBreakdown = Field(default_factory=ConfidenceBreakdown)
    evidence: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    consumed_line_count: int = 0
    total_line_count: int = 0


class BaseLogParser(ABC):
    """Abstract base class for all deterministic language stack-trace parsers."""

    format_name: str = "generic"

    @abstractmethod
    def detect(self, text: str) -> float:
        """Returns a detection confidence score between 0.0 and 1.0."""
        pass

    @abstractmethod
    def parse(self, text: str) -> ParserOutput:
        """Parses the input text and extracts structured crash diagnostics."""
        pass
