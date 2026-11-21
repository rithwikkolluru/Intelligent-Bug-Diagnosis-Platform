from __future__ import annotations

import re

from app.agents.log_analysis.heuristics import is_application_code, unescape_log_text
from app.agents.log_analysis.parsers.base import BaseLogParser, ParserOutput
from app.agents.log_analysis.schemas import (
    ConfidenceBreakdown,
    ExceptionChainItem,
    ExceptionInfo,
    FailurePoint,
    Frame,
)

# Java stack trace patterns
JAVA_EXCEPTION_HEADER_RE = re.compile(
    r"^(?:(?:\[?[A-Z]{4,8}\]?\s*|\d{4}-\d{2}-\d{2}[^\n]*?\s*)?)?"
    r"(?:Exception in thread \"[^\"]+\"\s+)?([a-zA-Z_$][a-zA-Z0-9_$.]*?(?:Exception|Error|Throwable))"
    r"(?::\s*(.*))?$",
    re.MULTILINE,
)

JAVA_FRAME_RE = re.compile(
    r"^\s*at\s+([a-zA-Z0-9_$<>/]+(?:\.[a-zA-Z0-9_$<>/]+)*)\.([a-zA-Z0-9_$<>/]+)"
    r"\((?:([^:()\s]+):(\d+)|(Native Method)|(Unknown Source))\)",
    re.MULTILINE,
)

CAUSED_BY_RE = re.compile(
    r"^Caused by:\s+([a-zA-Z_$][a-zA-Z0-9_$.]*?(?:Exception|Error|Throwable))(?::\s*(.*))?$"
)


class JavaLogParser(BaseLogParser):
    """Deterministic parser for standard Java stack traces, Caused by chains, and suppressed exceptions."""

    format_name = "java"

    def detect(self, text: str) -> float:
        if not text:
            return 0.0
        cleaned = unescape_log_text(text)
        score = 0.0
        if "at " in cleaned and ("(" in cleaned and ")" in cleaned):
            matches = JAVA_FRAME_RE.findall(cleaned)
            if matches:
                score += min(0.6, len(matches) * 0.2)
        if JAVA_EXCEPTION_HEADER_RE.search(cleaned):
            score += 0.3
        if "Caused by:" in cleaned:
            score += 0.2
        return min(1.0, score)

    def parse(self, text: str) -> ParserOutput:
        cleaned = unescape_log_text(text)
        lines = cleaned.splitlines()

        exception_chain: list[ExceptionChainItem] = []
        raw_frames: list[Frame] = []
        evidence: dict[str, str] = {}
        warnings: list[str] = []

        primary_exception: ExceptionInfo | None = None
        primary_message: str = ""
        current_cause_frames: list[Frame] = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # 1. Caused by header
            caused_match = CAUSED_BY_RE.match(line_str)
            if caused_match:
                cause_type, cause_msg = caused_match.group(1), (caused_match.group(2) or "").strip()
                exception_chain.append(ExceptionChainItem(type=cause_type, message=cause_msg))
                # For Caused by, the inner frames are the immediate failure point
                current_cause_frames = []
                continue

            # 2. Main exception header
            header_match = JAVA_EXCEPTION_HEADER_RE.match(line_str)
            if header_match and primary_exception is None and not line_str.startswith("at "):
                full_name = header_match.group(1)
                msg = (header_match.group(2) or "").strip()
                simple = full_name.split(".")[-1]
                primary_exception = ExceptionInfo(fully_qualified=full_name, simple_name=simple)
                primary_message = msg
                exception_chain.append(ExceptionChainItem(type=full_name, message=msg))
                evidence["exception_header"] = line_str
                continue

            # 3. Stack frame line: at com.foo.Bar.method(File.java:42)
            frame_match = JAVA_FRAME_RE.match(line_str)
            if frame_match:
                pkg_or_class = frame_match.group(1)
                method_name = frame_match.group(2)
                file_name = frame_match.group(3)
                line_no = int(frame_match.group(4)) if frame_match.group(4) else None
                class_simple = pkg_or_class.split(".")[-1]
                is_app = is_application_code(file_name, pkg_or_class)

                frame = Frame(
                    file=file_name,
                    cls=class_simple,
                    method=method_name,
                    line=line_no,
                    module_or_package=pkg_or_class,
                    is_application_code=is_app,
                    raw_frame=line_str,
                )
                raw_frames.append(frame)
                current_cause_frames.append(frame)

        if not primary_exception and exception_chain:
            first = exception_chain[0]
            simple = first.type.split(".")[-1]
            primary_exception = ExceptionInfo(fully_qualified=first.type, simple_name=simple)
            primary_message = first.message
        elif not primary_exception:
            primary_exception = ExceptionInfo(fully_qualified="java.lang.Throwable", simple_name="Throwable")

        # In Java, the innermost cause (last in Caused by chain) is the true root cause
        root_cause = exception_chain[-1] if exception_chain else ExceptionChainItem(
            type=primary_exception.fully_qualified, message=primary_message
        )

        # Failure point selection: prefer frames from the innermost Caused by block if present
        target_frames = current_cause_frames if current_cause_frames else raw_frames
        failure_point: FailurePoint | None = None

        # Look for topmost application frame with known source file
        for f in target_frames:
            if f.is_application_code and f.file:
                failure_point = FailurePoint(
                    file=f.file,
                    cls=f.cls,
                    method=f.method,
                    line=f.line,
                    column=f.column,
                    module_or_package=f.module_or_package,
                    is_application_code=True,
                    raw_frame=f.raw_frame,
                )
                evidence["failure_frame"] = f.raw_frame
                break

        # If not found, any application frame
        if failure_point is None:
            for f in target_frames:
                if f.is_application_code:
                    failure_point = FailurePoint(
                        file=f.file,
                        cls=f.cls,
                        method=f.method,
                        line=f.line,
                        column=f.column,
                        module_or_package=f.module_or_package,
                        is_application_code=True,
                        raw_frame=f.raw_frame,
                    )
                    evidence["failure_frame"] = f.raw_frame
                    break

        # If no application frame, take topmost raw frame
        if failure_point is None and target_frames:
            top = target_frames[0]
            failure_point = FailurePoint(
                file=top.file,
                cls=top.cls,
                method=top.method,
                line=top.line,
                column=top.column,
                module_or_package=top.module_or_package,
                is_application_code=False,
                raw_frame=top.raw_frame,
            )
            evidence["failure_frame"] = top.raw_frame

        # In Java stack traces, top is the failure; normalise code_path to entry-to-failure order
        code_path = list(reversed(raw_frames))

        has_line_nos = any(f.line is not None for f in raw_frames)
        breakdown = ConfidenceBreakdown(
            exception_type_parsed=bool(primary_exception.simple_name and primary_exception.simple_name != "Throwable"),
            error_message_extracted=bool(primary_message),
            frames_parsed_count=len(raw_frames),
            line_numbers_present=has_line_nos,
            application_frame_found=any(f.is_application_code for f in raw_frames),
            chain_consistent=len(exception_chain) > 0,
            parser_fully_consumed=len(raw_frames) > 0,
            llm_fallback_used=False,
        )

        return ParserOutput(
            detected_format=self.format_name,
            exception_type=primary_exception,
            error_message=primary_message,
            failure_point=failure_point,
            frames=code_path,
            exception_chain=exception_chain,
            root_cause_exception=root_cause,
            confidence_breakdown=breakdown,
            evidence=evidence,
            warnings=warnings,
            consumed_line_count=len(raw_frames),
            total_line_count=len(lines),
        )
