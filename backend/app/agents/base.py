from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.redaction import redact_secrets

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AgentInput(BaseModel):
    """Shared input payload passed to any platform diagnosis or triage agent."""

    bug_id: int | None = None
    title: str = Field(default="", description="Bug report title or summary")
    description: str = Field(default="", description="Observed vs expected behavior, reproduction steps")
    stack_trace: str | None = Field(default=None, description="Raw stack trace or exception trace")
    error_logs: str | None = Field(default=None, description="Log lines, HTTP errors, system context")
    programming_language: str | None = Field(default=None, description="Reported or detected programming language")
    project: str | None = Field(default=None, description="Source project name if known (e.g. mozilla, apache, eclipse)")
    source_type: str = Field(default="paste", description="Input ingestion source: paste | upload")

    @property
    def is_empty(self) -> bool:
        return not bool(
            (self.title and self.title.strip())
            or (self.description and self.description.strip())
            or (self.stack_trace and self.stack_trace.strip())
            or (self.error_logs and self.error_logs.strip())
        )


class AgentResult(BaseModel, Generic[T]):
    """Standardized result envelope produced by all platform agents."""

    agent_name: str
    status: Literal["ok", "partial", "skipped", "failed"]
    output: T | None = None
    warnings: list[str] = Field(default_factory=list)
    error: dict[str, str] | None = None
    duration_ms: float = 0.0
    provenance: dict[str, Any] = Field(default_factory=dict)


def sanitize_and_prepare_content(raw_text: str, max_chars: int | None = None) -> tuple[str, list[str]]:
    """Enforces safety rules on untrusted user text before passing it to any agent or LLM.

    1. Secondary Redaction Safety Net: Redacts any passwords/tokens that leaked through.
    2. Head-and-Tail Truncation: Caps oversized input, preserving beginning and end context.
    3. Untrusted Data Delimiting: Wraps the text inside explicit data boundaries.
    """
    settings = get_settings()
    limit = max_chars or settings.MAX_INPUT_CHARS
    warnings: list[str] = []

    if not raw_text:
        return "", warnings

    # 1. Redaction safety net
    cleaned_text, redact_count = redact_secrets(raw_text)
    if redact_count > 0:
        warnings.append(f"SAFETY_NET_REDACTED_{redact_count}_SECRETS")

    # 2. Head-and-tail truncation rule
    if len(cleaned_text) > limit:
        half = limit // 2
        truncated_count = len(cleaned_text) - limit
        head = cleaned_text[:half]
        tail = cleaned_text[-half:]
        cleaned_text = (
            f"{head}\n\n[... Truncated {truncated_count} characters from middle of input ...]\n\n{tail}"
        )
        warnings.append(f"INPUT_TRUNCATED_{truncated_count}_CHARS")

    # 3. Delimit untrusted content
    wrapped = (
        "<untrusted_bug_report>\n"
        f"{cleaned_text}\n"
        "</untrusted_bug_report>"
    )

    return wrapped, warnings


class BaseAgent(ABC, Generic[T]):
    """Abstract base class for all platform agents with safe exception containment."""

    agent_name: str = "base_agent"
    prompt_version: str = "v1"

    def run(self, input_data: AgentInput) -> AgentResult[T]:
        start_t = time.perf_counter()

        if input_data.is_empty:
            return AgentResult(
                agent_name=self.agent_name,
                status="skipped",
                output=None,
                warnings=["EMPTY_INPUT"],
                error=None,
                duration_ms=(time.perf_counter() - start_t) * 1000.0,
                provenance={"method": "rule", "prompt_version": self.prompt_version},
            )

        try:
            return self._execute(input_data, start_t)
        except Exception as exc:
            logger.exception("Agent '%s' failed unexpectedly during execution: %s", self.agent_name, exc)
            return AgentResult(
                agent_name=self.agent_name,
                status="failed",
                output=None,
                warnings=[],
                error={"code": exc.__class__.__name__, "message": str(exc)},
                duration_ms=(time.perf_counter() - start_t) * 1000.0,
                provenance={"method": "error", "prompt_version": self.prompt_version},
            )

    @abstractmethod
    def _execute(self, input_data: AgentInput, start_time: float) -> AgentResult[T]:
        """Internal execution logic to be implemented by concrete agents."""
        pass
