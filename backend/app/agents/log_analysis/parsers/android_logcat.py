from __future__ import annotations

import re

from app.agents.log_analysis.heuristics import unescape_log_text
from app.agents.log_analysis.parsers.base import BaseLogParser, ParserOutput
from app.agents.log_analysis.parsers.java import JavaLogParser

ANDROID_RUNTIME_RE = re.compile(
    r"(?:E/AndroidRuntime|AndroidRuntime\s*:\s*FATAL EXCEPTION|\bFATAL EXCEPTION:\s*main)",
    re.IGNORECASE,
)


class AndroidLogcatParser(BaseLogParser):
    """Deterministic parser for Android Logcat dumps wrapping Java VM crashes."""

    format_name = "android_logcat"

    def __init__(self):
        self._java_parser = JavaLogParser()

    def detect(self, text: str) -> float:
        if not text:
            return 0.0
        cleaned = unescape_log_text(text)
        if ANDROID_RUNTIME_RE.search(cleaned):
            return 0.95
        return 0.0

    def parse(self, text: str) -> ParserOutput:
        cleaned = unescape_log_text(text)
        lines = []
        for line in cleaned.splitlines():
            stripped = re.sub(r"^\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+\d+\s+[VDIWEF]\s+[^:]*:\s*", "", line)
            stripped = re.sub(r"^(?:[VDIWEF]/AndroidRuntime:\s*|AndroidRuntime\s*:\s*)", "", stripped)
            lines.append(stripped)

        java_text = "\n".join(lines)
        output = self._java_parser.parse(java_text)
        output.detected_format = self.format_name
        return output
