from __future__ import annotations

import logging
import re
import time

from app.agents.base import AgentInput, AgentResult, BaseAgent, sanitize_and_prepare_content
from app.agents.log_analysis.heuristics import unescape_log_text
from app.agents.log_analysis.parsers import detect_best_parser
from app.agents.log_analysis.schemas import (
    ConfidenceBreakdown,
    LogAnalysisResult,
)
from app.agents.prompt_registry import get_prompt_registry
from app.llm.client import LLMClient, get_llm_client
from app.llm.exceptions import LLMUnavailableError

logger = logging.getLogger(__name__)

# Max frames to retain in output to avoid bloating results
MAX_ALLOWED_FRAMES = 100

# Pattern for detecting binary garbage
BINARY_GARBAGE_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")


def compute_log_confidence(breakdown: ConfidenceBreakdown) -> float:
    """Calculates deterministic confidence based on evidence signals."""
    score = 0.0
    if breakdown.exception_type_parsed:
        score += 0.25
    if breakdown.error_message_extracted:
        score += 0.15
    if breakdown.frames_parsed_count > 0:
        score += 0.20 if breakdown.frames_parsed_count >= 2 else 0.10
    if breakdown.line_numbers_present:
        score += 0.15
    if breakdown.application_frame_found:
        score += 0.15
    if breakdown.chain_consistent:
        score += 0.10

    score = min(1.0, max(0.0, score))

    # Capped when relying on LLM fallback
    if breakdown.llm_fallback_used:
        score = min(0.75, score)

    return round(score, 2)


class LogAnalysisAgent(BaseAgent[LogAnalysisResult]):
    """Analyzes stack traces, crash dumps, and error logs.

    Primary Path: Deterministic language-specific parsers.
    Fallback Path: LLM fallback under strict no-silent-override rules.
    """

    agent_name = "log_analysis"
    prompt_version = "v1"

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client
        self.prompt_registry = get_prompt_registry()

    def _get_active_client(self) -> LLMClient:
        if self.llm_client is not None:
            return self.llm_client
        return get_llm_client()

    def _execute(self, input_data: AgentInput, start_time: float) -> AgentResult[LogAnalysisResult]:
        # 1. Determine target log text (combine stack trace and error logs if present)
        log_content = ""
        if input_data.stack_trace and input_data.stack_trace.strip():
            log_content = input_data.stack_trace.strip()
            if input_data.error_logs and input_data.error_logs.strip():
                log_content = f"{input_data.error_logs.strip()}\n\n{log_content}"
        elif input_data.error_logs and input_data.error_logs.strip():
            log_content = input_data.error_logs.strip()
        elif input_data.description and any(
            hint in input_data.description
            for hint in ["Exception", "Error", "Traceback", "at ", "#0 ", "panic:", "File \""]
        ):
            # Log trace embedded in description
            log_content = input_data.description.strip()
        else:
            # Description-only input with no stack trace or logs
            return AgentResult(
                agent_name=self.agent_name,
                status="skipped",
                output=None,
                warnings=["NO_LOG_OR_STACK_TRACE_DETECTED"],
                error=None,
                duration_ms=(time.perf_counter() - start_time) * 1000.0,
                provenance={"method": "rule", "prompt_version": self.prompt_version},
            )

        # 2. Pre-process and sanitize text
        unescaped = unescape_log_text(log_content)
        warnings: list[str] = []

        if BINARY_GARBAGE_RE.search(unescaped):
            unescaped = BINARY_GARBAGE_RE.sub("?", unescaped)
            warnings.append("BINARY_OR_UNPRINTABLE_CHARACTERS_FILTERED")

        # 3. Detect and run best deterministic parser
        best_parser, detection_score = detect_best_parser(unescaped)
        parser_output = best_parser.parse(unescaped)
        warnings.extend(parser_output.warnings)

        # Check for truncated trace marker
        if "... " in unescaped and "more" in unescaped:
            warnings.append("TRUNCATED_STACK_TRACE_WITH_MORE_FRAMES")

        # Cap frames if excessively large
        final_frames = parser_output.frames
        if len(final_frames) > MAX_ALLOWED_FRAMES:
            final_frames = final_frames[-MAX_ALLOWED_FRAMES:]
            warnings.append(f"STACK_TRACE_CAPPED_AT_{MAX_ALLOWED_FRAMES}_FRAMES")

        # Initial confidence computation
        initial_confidence = compute_log_confidence(parser_output.confidence_breakdown)

        # Determine if LLM fallback is needed (low confidence or missing key attributes)
        needs_llm_fallback = (
            detection_score < 0.4
            or initial_confidence < 0.5
            or not parser_output.exception_type.simple_name
            or parser_output.failure_point is None
        )

        provenance = {
            "method": "rule",
            "detected_parser": best_parser.format_name,
            "detection_score": detection_score,
            "prompt_version": self.prompt_version,
        }

        # 4. LLM Fallback (if needed and available)
        final_exception = parser_output.exception_type
        final_message = parser_output.error_message
        final_failure = parser_output.failure_point
        final_format = parser_output.detected_format
        breakdown = parser_output.confidence_breakdown

        if needs_llm_fallback:
            try:
                client = self._get_active_client()
                system_prompt = self.prompt_registry.get_prompt("log_analysis", self.prompt_version)
                wrapped_user_text, sanitize_warns = sanitize_and_prepare_content(unescaped, max_chars=8000)
                warnings.extend(sanitize_warns)

                llm_resp = client.generate_structured(
                    system_prompt=system_prompt,
                    user_content=wrapped_user_text,
                    response_model=LogAnalysisResult,
                    prompt_version=self.prompt_version,
                )
                llm_data = llm_resp.data

                # NO-SILENT-OVERRIDE RULE:
                # 1. Exception Type: keep parser if present; else use LLM
                if not final_exception.simple_name and llm_data.exception_type.simple_name:
                    final_exception = llm_data.exception_type
                elif (
                    final_exception.simple_name
                    and llm_data.exception_type.simple_name
                    and final_exception.simple_name != llm_data.exception_type.simple_name
                ):
                    warnings.append(
                        f"CONFLICT_LLM_EXCEPTION_TYPE_IGNORED: Parser had '{final_exception.simple_name}', LLM suggested '{llm_data.exception_type.simple_name}'"
                    )

                # 2. Failure Point: keep parser if present; else use LLM
                if final_failure is None and llm_data.failure_point is not None:
                    final_failure = llm_data.failure_point

                # 3. Error Message: keep parser if present; else use LLM
                if not final_message and llm_data.error_message:
                    final_message = llm_data.error_message

                if final_format in {"generic_log", "unknown"} and llm_data.detected_format != "unknown":
                    final_format = llm_data.detected_format

                breakdown.llm_fallback_used = True
                provenance.update({
                    "method": "hybrid" if detection_score >= 0.2 else "llm",
                    "provider": llm_resp.provider,
                    "model": llm_resp.model,
                    "cache_hit": llm_resp.cache_hit,
                })
            except (LLMUnavailableError, Exception) as llm_exc:
                logger.info("LLM fallback unavailable or failed (%s). Continuing with rule result.", llm_exc)
                warnings.append(f"LLM_FALLBACK_SKIPPED_{llm_exc.__class__.__name__}")

        # Compute final calibrated confidence
        final_confidence = compute_log_confidence(breakdown)

        status_result = "ok"
        if not final_failure and not final_exception.simple_name:
            status_result = "partial"

        result_model = LogAnalysisResult(
            detected_format=final_format,
            exception_type=final_exception,
            error_message=final_message,
            failure_point=final_failure,
            code_path=final_frames,
            exception_chain=parser_output.exception_chain,
            root_cause_exception=parser_output.root_cause_exception,
            other_traces_count=0,
            primary_trace_selection_reason="last_active_crash_trace",
            confidence=final_confidence,
            confidence_breakdown=breakdown,
            evidence=parser_output.evidence,
            warnings=warnings,
        )

        return AgentResult(
            agent_name=self.agent_name,
            status=status_result,
            output=result_model,
            warnings=warnings,
            error=None,
            duration_ms=(time.perf_counter() - start_time) * 1000.0,
            provenance=provenance,
        )
