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

# Go panic:
# panic: runtime error: index out of range [5] with length 3
# goroutine 1 [running]:
# main.processItem(0x10a2?, {0x140001?, 0x0?})
# 	/app/main.go:42 +0x68
GO_PANIC_RE = re.compile(r"^panic:\s*(.*)$")
GO_GOROUTINE_RE = re.compile(r"^goroutine\s+\d+\s+\[([^\]]+)\]:")
GO_FILE_LINE_RE = re.compile(r"^\s*([^\s:]+):(\d+)(?:\s+\+0x[0-9a-fA-F]+)?$")


class GoLogParser(BaseLogParser):
    """Deterministic parser for Go panic and goroutine stack traces."""

    format_name = "go"

    def detect(self, text: str) -> float:
        if not text:
            return 0.0
        cleaned = unescape_log_text(text)
        score = 0.0
        if "panic:" in cleaned:
            score += 0.5
        if "goroutine " in cleaned and "[running]" in cleaned:
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

        idx = 0
        while idx < len(lines):
            line = lines[idx].strip()
            if not line:
                idx += 1
                continue

            panic_match = GO_PANIC_RE.match(line)
            if panic_match and primary_exception is None:
                msg = panic_match.group(1).strip()
                primary_exception = ExceptionInfo(fully_qualified="panic", simple_name="panic")
                primary_message = msg
                evidence["panic_line"] = line
                idx += 1
                continue

            # Go function line followed by file:line
            if idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                fl_match = GO_FILE_LINE_RE.match(next_line)
                if fl_match and not line.startswith("goroutine ") and not line.startswith("panic:"):
                    func_name = line.split("(")[0].strip()
                    file_path = fl_match.group(1)
                    line_no = int(fl_match.group(2))
                    is_app = is_application_code(file_path, func_name)

                    frame = Frame(
                        file=file_path,
                        cls=func_name.rsplit(".", 1)[0] if "." in func_name else None,
                        method=func_name.rsplit(".", 1)[1] if "." in func_name else func_name,
                        line=line_no,
                        is_application_code=is_app,
                        raw_frame=f"{line}\n\t{next_line}",
                    )
                    raw_frames.append(frame)
                    idx += 2
                    continue

            idx += 1

        if not primary_exception:
            primary_exception = ExceptionInfo(fully_qualified="panic", simple_name="panic")

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
            exception_type_parsed=True,
            error_message_extracted=bool(primary_message),
            frames_parsed_count=len(raw_frames),
            line_numbers_present=len(raw_frames) > 0,
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
