from app.agents.log_analysis.parsers.android_logcat import AndroidLogcatParser
from app.agents.log_analysis.parsers.base import BaseLogParser, ParserOutput
from app.agents.log_analysis.parsers.cpp_gdb import CppGdbLogParser
from app.agents.log_analysis.parsers.dotnet import DotNetLogParser
from app.agents.log_analysis.parsers.generic_log import GenericLogParser
from app.agents.log_analysis.parsers.go import GoLogParser
from app.agents.log_analysis.parsers.java import JavaLogParser
from app.agents.log_analysis.parsers.javascript_firefox import JavaScriptFirefoxLogParser
from app.agents.log_analysis.parsers.javascript_v8 import JavaScriptV8LogParser
from app.agents.log_analysis.parsers.python import PythonLogParser

ALL_PARSERS: list[BaseLogParser] = [
    AndroidLogcatParser(),
    PythonLogParser(),
    JavaLogParser(),
    JavaScriptV8LogParser(),
    JavaScriptFirefoxLogParser(),
    CppGdbLogParser(),
    DotNetLogParser(),
    GoLogParser(),
    GenericLogParser(),
]


def detect_best_parser(text: str) -> tuple[BaseLogParser, float]:
    """Scores all deterministic parsers on input and returns (best_parser, confidence_score)."""
    best_parser: BaseLogParser = ALL_PARSERS[-1]  # GenericLogParser default
    best_score = 0.0

    for parser in ALL_PARSERS:
        score = parser.detect(text)
        if score > best_score:
            best_score = score
            best_parser = parser

    return best_parser, best_score


__all__ = [
    "BaseLogParser",
    "ParserOutput",
    "JavaLogParser",
    "PythonLogParser",
    "JavaScriptV8LogParser",
    "JavaScriptFirefoxLogParser",
    "CppGdbLogParser",
    "DotNetLogParser",
    "GoLogParser",
    "AndroidLogcatParser",
    "GenericLogParser",
    "ALL_PARSERS",
    "detect_best_parser",
]
