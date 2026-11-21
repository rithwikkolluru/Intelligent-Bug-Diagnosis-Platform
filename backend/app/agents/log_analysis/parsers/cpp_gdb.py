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

# GDB frame:
# #0  0x00007ffff7a24c37 in __GI_raise (sig=sig@entry=6) at ../sysdeps/unix/sysv/linux/raise.c:51
# #1  0x0000000000401824 in PacketBuffer::release (this=0x604010) at net/buffer.cpp:112
GDB_FRAME_RE = re.compile(
    r"^\s*#(\d+)\s+(?:0x[0-9a-fA-F]+\s+in\s+)?([a-zA-Z0-9_$:~<>, *&]+)\s*(?:\([^)]*\))?\s+at\s+([^:\s]+):(\d+)",
    re.MULTILINE,
)

# Sanitizer header:
# ERROR: AddressSanitizer: heap-use-after-free on address 0x...
# Program received signal SIGSEGV, Segmentation fault.
CPP_SIGNAL_RE = re.compile(
    r"(?:Program received signal\s+(SIG[A-Z0-9]+)|ERROR:\s*([a-zA-Z]+Sanitizer):\s*([^\n]+)|(SIGSEGV|SIGABRT|SIGBUS|SIGFPE))",
    re.IGNORECASE,
)


class CppGdbLogParser(BaseLogParser):
    """Deterministic parser for C/C++ GDB backtraces, LLDB, and AddressSanitizer reports."""

    format_name = "cpp_gdb"

    def detect(self, text: str) -> float:
        if not text:
            return 0.0
        cleaned = unescape_log_text(text)
        score = 0.0
        if "#0 " in cleaned or "#01 " in cleaned or "#1 " in cleaned:
            matches = GDB_FRAME_RE.findall(cleaned)
            score += min(0.7, len(matches) * 0.3)
        if CPP_SIGNAL_RE.search(cleaned):
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

            sig_match = CPP_SIGNAL_RE.search(line_str)
            if sig_match and primary_exception is None:
                sig_name = sig_match.group(1) or sig_match.group(2) or sig_match.group(4) or "SIGSEGV"
                detail = sig_match.group(3) or line_str
                primary_exception = ExceptionInfo(fully_qualified=sig_name, simple_name=sig_name)
                primary_message = detail
                evidence["signal_header"] = line_str

            frame_match = GDB_FRAME_RE.match(line_str)
            if frame_match:
                func_name = frame_match.group(2).strip()
                file_path = frame_match.group(3).strip()
                line_no = int(frame_match.group(4))
                is_app = is_application_code(file_path, func_name)

                frame = Frame(
                    file=file_path,
                    cls=func_name.split("::")[0] if "::" in func_name else None,
                    method=func_name,
                    line=line_no,
                    is_application_code=is_app,
                    raw_frame=line_str,
                )
                raw_frames.append(frame)

        if not primary_exception:
            primary_exception = ExceptionInfo(fully_qualified="SIGSEGV", simple_name="SIGSEGV")
            primary_message = "Segmentation fault or unhandled native signal"

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
            exception_type_parsed=bool(primary_exception.simple_name),
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
