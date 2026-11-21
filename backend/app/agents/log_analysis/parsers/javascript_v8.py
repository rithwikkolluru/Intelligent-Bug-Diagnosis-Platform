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

JS_HEADER_RE = re.compile(
    r"^([a-zA-Z_$][a-zA-Z0-9_$]*(?:Error|Exception))(?::\s*(.*))?$",
    re.MULTILINE,
)

V8_FRAME_RE = re.compile(
    r"^\s*at\s+(?:async\s+)?(?:new\s+)?(?:([a-zA-Z0-9_$.<>\s]+)\s+)?\(?(?:(.*?):(\d+)(?::(\d+))?|\b(native|eval at [^\n]+)\b)\)?$",
    re.MULTILINE,
)


class JavaScriptV8LogParser(BaseLogParser):
    """Deterministic parser for Node.js, Chrome, and Chromium V8 stack traces."""

    format_name = "javascript_v8"

    def detect(self, text: str) -> float:
        if not text:
            return 0.0
        cleaned = unescape_log_text(text)
        score = 0.0
        if "at " in cleaned and (":" in cleaned and (")" in cleaned or "/" in cleaned)):
            matches = V8_FRAME_RE.findall(cleaned)
            score += min(0.7, len(matches) * 0.25)
        if JS_HEADER_RE.search(cleaned):
            score += 0.3
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

            # Header match
            header_match = JS_HEADER_RE.match(line_str)
            if header_match and primary_exception is None and not line_str.startswith("at "):
                full_name = header_match.group(1)
                msg = (header_match.group(2) or "").strip()
                primary_exception = ExceptionInfo(fully_qualified=full_name, simple_name=full_name)
                primary_message = msg
                evidence["exception_header"] = line_str
                continue

            # Frame match
            frame_match = V8_FRAME_RE.match(line_str)
            if frame_match:
                method_name = (frame_match.group(1) or "").strip()
                file_path = frame_match.group(2)
                line_no = int(frame_match.group(3)) if frame_match.group(3) else None
                col_no = int(frame_match.group(4)) if frame_match.group(4) else None

                if file_path and "eval at " in file_path:
                    eval_match = re.search(r"eval at (?:[^\s(]+)\s*\((.+?):(\d+)(?::(\d+))?\)", file_path)
                    if eval_match:
                        file_path = eval_match.group(1)
                        line_no = int(eval_match.group(2))
                        col_no = int(eval_match.group(3)) if eval_match.group(3) else None

                is_app = is_application_code(file_path, method_name)
                frame = Frame(
                    file=file_path,
                    cls=None,
                    method=method_name or None,
                    line=line_no,
                    column=col_no,
                    is_application_code=is_app,
                    raw_frame=line_str,
                )
                raw_frames.append(frame)

        if not primary_exception:
            primary_exception = ExceptionInfo(fully_qualified="Error", simple_name="Error")

        # In V8, top frame is the failure point; reverse to entry-to-failure order
        code_path = list(reversed(raw_frames))

        failure_point: FailurePoint | None = None
        for f in raw_frames:
            if f.is_application_code:
                failure_point = FailurePoint(
                    file=f.file,
                    cls=f.cls,
                    method=f.method,
                    line=f.line,
                    column=f.column,
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
                column=top.column,
                is_application_code=False,
                raw_frame=top.raw_frame,
            )
            evidence["failure_frame"] = top.raw_frame

        chain = [ExceptionChainItem(type=primary_exception.fully_qualified, message=primary_message)]
        has_lines = any(f.line is not None for f in raw_frames)
        breakdown = ConfidenceBreakdown(
            exception_type_parsed=bool(primary_exception.simple_name and primary_exception.simple_name != "Error"),
            error_message_extracted=bool(primary_message),
            frames_parsed_count=len(raw_frames),
            line_numbers_present=has_lines,
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
