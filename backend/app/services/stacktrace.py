from __future__ import annotations

import re


def detect_and_split(text: str) -> tuple[str, str | None, str | None]:
    if not text:
        return "", None, None

    text = text.strip()
    if not text:
        return "", None, None

    if re.search(r"Traceback \(most recent call last\):", text, re.IGNORECASE):
        match = re.search(r"Traceback \(most recent call last\):.*(?:\n\s*File .*|\n\s*.*?: .*|\s*$)", text, re.DOTALL)
        if match:
            trace = match.group(0)
            idx = text.find(trace)
            description = text[:idx].strip()
            return description, trace, "Python"

    java_pattern = r"(?is)(?:^|\n)(?:java\.[\w$.]+(?:Exception|Error|Throwable)|[\w$.]+(?:Exception|Error|Throwable))(?:\s*:\s*.*)?(?:\n\s*at [^\n]+\([^\n]+:\d+(?::\d+)?\))*?(?:\n\s*Caused by:.*)?"
    java_match = re.search(java_pattern, text)
    if java_match:
        trace = java_match.group(0).lstrip()
        idx = text.find(trace)
        description = text[:idx].strip()
        return description, trace, "Java"

    js_pattern = r"(?is)(?:^|\n)Error: .*?(?:\n\s*at [^\n]+\([^\n]+:\d+:\d+\)|\n\s*at [^\n]+\([^\n]+:\d+\))+"
    js_match = re.search(js_pattern, text)
    if js_match:
        trace = js_match.group(0).lstrip()
        idx = text.find(trace)
        description = text[:idx].strip()
        return description, trace, "JavaScript"

    gdb_pattern = r"(?m)(?:^#\d+\s+0x[0-9a-fA-F]+\s+in\s+.*?\s+at\s+.*?:\d+.*(?:\n|$))+"
    gdb_match = re.search(gdb_pattern, text)
    if gdb_match:
        trace = gdb_match.group(0).strip()
        idx = text.find(trace)
        description = text[:idx].strip()
        return description, trace, "C/C++"

    return text, None, None
