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

# .NET frame:
#    at Namespace.Class.Method(ParamType param) in C:\Source\App\File.cs:line 42
#    at Namespace.Class.<AsyncMethod>d__1.MoveNext()
DOTNET_FRAME_RE = re.compile(
    r"^\s*at\s+([a-zA-Z0-9_$.<>]+)\s*(?:\([^)]*\))?(?:\s+in\s+(.+?):line\s+(\d+))?"
)

DOTNET_EXCEPTION_RE = re.compile(
    r"^(System\.[a-zA-Z0-9_$.]+Exception|Microsoft\.[a-zA-Z0-9_$.]+Exception)(?::\s*(.*))?$"
)


class DotNetLogParser(BaseLogParser):
    """Deterministic parser for C# / .NET CLR stack traces."""

    format_name = "dotnet"

    def detect(self, text: str) -> float:
        if not text:
            return 0.0
        cleaned = unescape_log_text(text)
        score = 0.0
        if "System." in cleaned and "Exception" in cleaned:
            score += 0.4
        if ":line " in cleaned:
            score += 0.4
        return min(1.0, score)

    def parse(self, text: str) -> ParserOutput:
        cleaned = unescape_log_text(text)
        lines = cleaned.splitlines()

        raw_frames: list[Frame] = []
        evidence: dict[str, str] = {}
        warnings: list[str] = []

        primary_exception: ExceptionInfo | None = None
        primary_message: str = ""

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            exc_match = DOTNET_EXCEPTION_RE.match(line_str)
            if exc_match and primary_exception is None and not line_str.startswith("at "):
                full_name = exc_match.group(1)
                msg = (exc_match.group(2) or "").strip()
                simple = full_name.split(".")[-1]
                primary_exception = ExceptionInfo(fully_qualified=full_name, simple_name=simple)
                primary_message = msg
                evidence["exception_header"] = line_str
                continue

            frame_match = DOTNET_FRAME_RE.match(line_str)
            if frame_match:
                func_name = frame_match.group(1).strip()
                file_path = (frame_match.group(2) or "").strip() or None
                line_no = int(frame_match.group(3)) if frame_match.group(3) else None
                is_app = is_application_code(file_path, func_name)

                frame = Frame(
                    file=file_path,
                    cls=func_name.rsplit(".", 1)[0] if "." in func_name else None,
                    method=func_name.rsplit(".", 1)[1] if "." in func_name else func_name,
                    line=line_no,
                    is_application_code=is_app,
                    raw_frame=line_str,
                )
                raw_frames.append(frame)

        if not primary_exception:
            primary_exception = ExceptionInfo(fully_qualified="System.Exception", simple_name="Exception")

        code_path = list(reversed(raw_frames))

        failure_point: FailurePoint | None = None
        for f in raw_frames:
            if f.is_application_code:
                failure_point = FailurePoint(
                    file=f.file,
                    cls=f.cls,
                    method=f.method,
                    line=f.line,
                    is_application_code=True,
                    raw_frame=f.raw_frame,
                )
                evidence["failure_frame"] = f.raw_frame
                break

        if failure_point is None and raw_frames:
            top = raw_frames[0]
            failure_point = FailurePoint(
                file=top.file,
                cls=top.cls,
                method=top.method,
                line=top.line,
                is_application_code=False,
                raw_frame=top.raw_frame,
            )
            evidence["failure_frame"] = top.raw_frame

        chain = [ExceptionChainItem(type=primary_exception.fully_qualified, message=primary_message)]
        breakdown = ConfidenceBreakdown(
            exception_type_parsed=bool(primary_exception.simple_name and primary_exception.simple_name != "Exception"),
            error_message_extracted=bool(primary_message),
            frames_parsed_count=len(raw_frames),
            line_numbers_present=any(f.line is not None for f in raw_frames),
            application_frame_found=any(f.is_application_code for f in raw_frames),
            chain_consistent=True,
            parser_fully_consumed=len(raw_frames) > 0,
            llm_fallback_used=False,
        )

        return ParserOutput(
            detected_format=self.format_name,
            exception_type=primary_exception,
            error_message=primary_message,
            failure_point=failure_point,
            frames=code_path,
            exception_chain=chain,
            root_cause_exception=chain[0],
            confidence_breakdown=breakdown,
            evidence=evidence,
            warnings=warnings,
            consumed_line_count=len(raw_frames),
            total_line_count=len(lines),
        )
