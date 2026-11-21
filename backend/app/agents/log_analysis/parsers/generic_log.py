from __future__ import annotations

import re
from collections import Counter

from app.agents.log_analysis.heuristics import unescape_log_text
from app.agents.log_analysis.parsers.base import BaseLogParser, ParserOutput
from app.agents.log_analysis.schemas import (
    ConfidenceBreakdown,
    ExceptionChainItem,
    ExceptionInfo,
)

ERROR_LEVEL_RE = re.compile(
    r"\b(FATAL|CRITICAL|SEVERE|ERROR|PANIC)\b",
    re.IGNORECASE,
)


class GenericLogParser(BaseLogParser):
    """Deterministic parser for structured application logs without stack traces.

    Extracts high-severity error entries, collapses repetitive failure sequences,
    and isolates the primary error line.
    """

    format_name = "generic_log"

    def detect(self, text: str) -> float:
        if not text:
            return 0.0
        cleaned = unescape_log_text(text)
        if ERROR_LEVEL_RE.search(cleaned):
            return 0.35
        return 0.1

    def parse(self, text: str) -> ParserOutput:
        cleaned = unescape_log_text(text)
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]

        error_lines: list[str] = []
        for line in lines:
            if ERROR_LEVEL_RE.search(line):
                error_lines.append(line)

        evidence: dict[str, str] = {}
        warnings: list[str] = []

        if not error_lines:
            error_lines = lines[:1] if lines else []

        # Count repeat messages
        counts = Counter(error_lines)
        primary_line = error_lines[-1] if error_lines else ""
        repeat_count = counts[primary_line]
        if repeat_count > 1:
            warnings.append(f"REPEATED_ERROR_LINE_{repeat_count}_TIMES")

        evidence["error_line"] = primary_line

        # Simple exception or error identification
        exc_type = "LogFailure"
        for candidate in ["TimeoutException", "ConnectionRefused", "DatabaseError", "AuthError", "NotFound"]:
            if candidate.lower() in primary_line.lower():
                exc_type = candidate
                break

        primary_exception = ExceptionInfo(fully_qualified=exc_type, simple_name=exc_type)
        chain = [ExceptionChainItem(type=exc_type, message=primary_line)]

        breakdown = ConfidenceBreakdown(
            exception_type_parsed=False,
            error_message_extracted=bool(primary_line),
            frames_parsed_count=0,
            line_numbers_present=False,
            application_frame_found=False,
            chain_consistent=True,
            parser_fully_consumed=False,
            llm_fallback_used=False,
        )

        return ParserOutput(
            detected_format=self.format_name,
            exception_type=primary_exception,
            error_message=primary_line,
            failure_point=None,
            frames=[],
            exception_chain=chain,
            root_cause_exception=chain[0],
            confidence_breakdown=breakdown,
            evidence=evidence,
            warnings=warnings,
            consumed_line_count=len(error_lines),
            total_line_count=len(lines),
        )
