from __future__ import annotations

import html
import re

from app.agents.log_analysis.schemas import Frame

# ANSI escape sequence remover
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Common log prefix patterns (timestamp, level, thread name, pid)
LOG_PREFIX_RE = re.compile(
    r"^(?:\[?\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?Z?\]?\s*)?"  # ISO / common timestamp
    r"(?:(?:INFO|DEBUG|WARN|WARNING|ERROR|FATAL|SEVERE|CRITICAL|NOTICE)\s*)?"  # Log levels
    r"(?:\[[\w\-.: ]+\]\s*)?"  # Thread name [http-nio-8080-exec-1]
    r"(?:[\w\-.]+:\s*)?"  # Logger name
    r"(?:[-:]\s*)?"
)

# Line-number gutters from IDE copy-pastes (e.g. " 42 |   at ...")
GUTTER_RE = re.compile(r"^\s*\d+\s*[|│]\s*")

# Framework/library path patterns indicating non-application infrastructure code
FRAMEWORK_PATTERNS = [
    # Java
    r"^java\.",
    r"^javax\.",
    r"^jdk\.",
    r"^sun\.",
    r"^com\.sun\.",
    r"^org\.springframework\.",
    r"^org\.apache\.catalina\.",
    r"^org\.apache\.tomcat\.",
    r"^org\.apache\.cxf\.",
    r"^org\.hibernate\.",
    r"^org\.eclipse\.osgi\.",
    r"^org\.junit\.",
    r"^junit\.",
    r"GeneratedMethodAccessor",
    r"\$\$EnhancerBySpringCGLIB",
    # Python
    r"/lib/python\d\.\d+/",
    r"/site-packages/",
    r"/dist-packages/",
    r"<frozen\s+importlib",
    r"/pytest/",
    r"/unittest/",
    # JavaScript / Node.js
    r"node_modules",
    r"node:internal",
    r"internal/modules",
    r"internal/process",
    r"react-dom\.development\.js",
    r"react\.development\.js",
    r"<anonymous>",
    r"<native>",
    r"eval at ",
    # C/C++ / system
    r"^/usr/lib",
    r"^/usr/include",
    r"^/lib/",
    r"libc\.so",
    r"libpthread",
    r"raise\.c",
    r"abort\.c",
    # .NET
    r"^System\.",
    r"^Microsoft\.",
    # Go
    r"/src/runtime/",
    r"^runtime/",
    r"^runtime\.",
    r"/usr/local/go/",
    r"^testing/",
]

FRAMEWORK_COMPILED = [re.compile(p, re.IGNORECASE) for p in FRAMEWORK_PATTERNS]


def unescape_log_text(raw_text: str) -> str:
    """Unescapes HTML entities, JSON newlines, and ANSI colors from raw input."""
    if not raw_text:
        return ""
    text = raw_text

    # HTML entity unescape (e.g. &lt; -> <, &quot; -> ")
    if "&" in text:
        text = html.unescape(text)

    # JSON newline unescape if text was double-escaped as literal \n or \r\n
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")

    # Strip ANSI color codes
    text = ANSI_ESCAPE_RE.sub("", text)

    # Normalize CRLF and solitary CR to \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    return text


def clean_log_line(line: str) -> str:
    """Strips timestamps, log-levels, thread prefixes, and IDE gutters from a line."""
    line = GUTTER_RE.sub("", line)
    return line


def is_application_code(file_path: str | None, package_or_class: str | None) -> bool:
    """Determines whether a stack frame belongs to user application code or third-party framework code."""
    check_targets = [str(file_path or ""), str(package_or_class or "")]
    for target in check_targets:
        if not target:
            continue
        for pattern in FRAMEWORK_COMPILED:
            if pattern.search(target):
                return False

    return True


def identify_failure_point(frames: list[Frame], raw_top_frame: Frame | None = None) -> Frame | None:
    """Selects the failure point.

    Decision rule:
    1. If application-code frames exist, the topmost application frame closest to the crash is selected.
    2. If no application frame exists (e.g. pure framework or system crash), the topmost raw frame is selected
       and marked with is_application_code = False.
    """
    if not frames:
        return raw_top_frame

    # Find the first application frame from the failure side
    for frame in frames:
        if frame.is_application_code:
            return frame

    # Fallback to the top frame
    fallback = frames[0].model_copy()
    fallback.is_application_code = False
    return fallback
