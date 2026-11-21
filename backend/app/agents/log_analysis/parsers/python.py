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

PYTHON_TRACEBACK_HEADER_RE = re.compile(r"Traceback\s+\(most recent call last\):", re.IGNORECASE)

PYTHON_FRAME_RE = re.compile(
    r'^\s*File\s+"([^"]+)",\s+line\s+(\d+)(?:,\s+in\s+([^\n]+))?',
    re.MULTILINE,
)

PYTHON_EXCEPTION_RE = re.compile(
    r"^([a-zA-Z_][a-zA-Z0-9_.]*(?:Error|Exception|Warning|Interrupt|Exit))(?::\s*(.*))?$",
    re.MULTILINE,
)

CHAIN_RE = re.compile(
    r"^(During handling of the above exception, another exception occurred:|The above exception was the direct cause of the following exception:)",
    re.IGNORECASE,
)


class PythonLogParser(BaseLogParser):
    """Deterministic parser for Python tracebacks, chained exceptions, and syntax error lines."""

    format_name = "python"

    def detect(self, text: str) -> float:
        if not text:
            return 0.0
        cleaned = unescape_log_text(text)
        score = 0.0
        if PYTHON_TRACEBACK_HEADER_RE.search(cleaned):
            score += 0.6
        if 'File "' in cleaned and ", line " in cleaned:
            matches = PYTHON_FRAME_RE.findall(cleaned)
            score += min(0.3, len(matches) * 0.1)
        if PYTHON_EXCEPTION_RE.search(cleaned):
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

        idx = 0
        while idx < len(lines):
            line = lines[idx].strip()

            # 1. Chained exception delimiter
            if CHAIN_RE.match(line):
                # When chained, the subsequent trace is the resulting exception
                idx += 1
                continue

            # 2. Stack frame: File "...", line N, in func
            frame_match = PYTHON_FRAME_RE.match(line)
            if frame_match:
                file_path = frame_match.group(1)
                line_no = int(frame_match.group(2))
                method_name = (frame_match.group(3) or "").strip()
                is_app = is_application_code(file_path, None)

                # Check if next line contains the code snippet
                raw_snippet = line
                if idx + 1 < len(lines) and not lines[idx + 1].strip().startswith("File "):
                    next_line = lines[idx + 1].strip()
                    if not PYTHON_EXCEPTION_RE.match(next_line) and not CHAIN_RE.match(next_line):
                        raw_snippet = f"{line}\n    {next_line}"
                        idx += 1

                frame = Frame(
                    file=file_path,
                    cls=None,
                    method=method_name,
                    line=line_no,
                    module_or_package=file_path.split("/")[-1].replace(".py", "") if "/" in file_path else None,
                    is_application_code=is_app,
                    raw_frame=raw_snippet,
                )
                raw_frames.append(frame)
                idx += 1
                continue

            # 3. Exception trailer line: e.g. KeyError: 'customer_id'
            exc_match = PYTHON_EXCEPTION_RE.match(line)
            if exc_match:
                exc_type = exc_match.group(1)
                msg = (exc_match.group(2) or "").strip()
                simple = exc_type.split(".")[-1]
                primary_exception = ExceptionInfo(fully_qualified=exc_type, simple_name=simple)
                primary_message = msg
                exception_chain.append(ExceptionChainItem(type=exc_type, message=msg))
                evidence["exception_line"] = line

            idx += 1

        if not primary_exception and exception_chain:
            last_item = exception_chain[-1]
            primary_exception = ExceptionInfo(fully_qualified=last_item.type, simple_name=last_item.type.split(".")[-1])
            primary_message = last_item.message
        elif not primary_exception:
            primary_exception = ExceptionInfo(fully_qualified="Exception", simple_name="Exception")

        # In Python tracebacks, the order is ALREADY entry point -> failure point!
        code_path = list(raw_frames)

        # Failure point is the last application frame in execution order (closest to failure)
        failure_point: FailurePoint | None = None
        for f in reversed(raw_frames):
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

        # Fallback to the absolute bottom frame
        if failure_point is None and raw_frames:
            bottom = raw_frames[-1]
            failure_point = FailurePoint(
                file=bottom.file,
                cls=bottom.cls,
                method=bottom.method,
                line=bottom.line,
                column=bottom.column,
                module_or_package=bottom.module_or_package,
                is_application_code=False,
                raw_frame=bottom.raw_frame,
            )
            evidence["failure_frame"] = bottom.raw_frame

        root_cause = exception_chain[0] if exception_chain else ExceptionChainItem(
            type=primary_exception.fully_qualified, message=primary_message
        )

        has_line_nos = any(f.line is not None for f in raw_frames)
        breakdown = ConfidenceBreakdown(
            exception_type_parsed=bool(primary_exception.simple_name and primary_exception.simple_name != "Exception"),
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
