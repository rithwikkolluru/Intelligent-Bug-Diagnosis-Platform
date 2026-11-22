from __future__ import annotations

import difflib
import re

# Top components derived from historical data (Phase 0 analysis)
VOCABULARY_BY_PROJECT: dict[str, list[str]] = {
    "mozilla": [
        "Core:DOM",
        "Core:Layout",
        "Core:JavaScript Engine",
        "Core:Graphics",
        "Core:Networking",
        "Core:Security",
        "Firefox:General",
        "Firefox:Address Bar",
        "Firefox:Bookmarks",
        "Firefox:Tabbed Browser",
        "Toolkit:General",
        "Toolkit:Storage",
        "Thunderbird:Mail Window",
    ],
    "eclipse": [
        "JDT:Core",
        "JDT:UI",
        "JDT:Debug",
        "Platform:UI",
        "Platform:Core",
        "Platform:SWT",
        "Platform:Ant",
        "Platform:Compare",
        "Platform:Debug",
        "Platform:Help",
        "PDE:UI",
    ],
    "apache": [
        "Tomcat:Catalina",
        "Tomcat:Coyote",
        "Tomcat:Jasper",
        "Tomcat:Connectors",
        "HTTPD:Core",
        "HTTPD:mod_ssl",
        "HTTPD:mod_proxy",
        "Lucene:Core",
        "Lucene:QueryParser",
        "Spark:Core",
        "Spark:SQL",
    ],
}

# General fallback vocabulary aggregated across projects
ALL_KNOWN_COMPONENTS = sorted(
    {c for comps in VOCABULARY_BY_PROJECT.values() for c in comps}
)

# Namespace / package to component mapping
PACKAGE_COMPONENT_MAP: dict[str, str] = {
    "org.apache.catalina": "Tomcat:Catalina",
    "org.apache.coyote": "Tomcat:Coyote",
    "org.apache.jasper": "Tomcat:Jasper",
    "org.apache.httpd": "HTTPD:Core",
    "org.apache.lucene": "Lucene:Core",
    "org.apache.spark": "Spark:Core",
    "org.eclipse.jdt.core": "JDT:Core",
    "org.eclipse.jdt.internal.ui": "JDT:UI",
    "org.eclipse.jdt.debug": "JDT:Debug",
    "org.eclipse.swt": "Platform:SWT",
    "org.eclipse.core": "Platform:Core",
    "org.eclipse.ui": "Platform:UI",
    "mozilla::dom": "Core:DOM",
    "js::": "Core:JavaScript Engine",
    "nsNet": "Core:Networking",
    "mozilla::net": "Core:Networking",
    "mozilla::layout": "Core:Layout",
    "mozilla::gfx": "Core:Graphics",
}


def normalize_component_name(raw: str) -> str:
    """Normalizes formatting, stripping whitespace and unifying separators."""
    if not raw:
        return "Unknown"
    norm = re.sub(r"\s+", " ", raw.strip())
    norm = norm.replace("::", ":").replace("/", ":")
    return norm


def match_component(
    text: str,
    project: str | None = None,
    trace_text: str | None = None,
) -> tuple[str, bool, list[str]]:
    """
    Attempts to identify the most likely component using:
    1. Package/namespace mapping on stack trace
    2. Exact or fuzzy match against project vocabulary
    3. General fallback vocabulary match
    """
    # 1. Check trace packages
    if trace_text:
        for pkg, comp in PACKAGE_COMPONENT_MAP.items():
            if pkg in trace_text:
                candidates = [c for c in ALL_KNOWN_COMPONENTS if c != comp][:3]
                return comp, True, candidates

    # Determine vocabulary to match against
    vocab = ALL_KNOWN_COMPONENTS
    if project and project.lower() in VOCABULARY_BY_PROJECT:
        vocab = VOCABULARY_BY_PROJECT[project.lower()]

    lower_text = text.lower() if text else ""

    # 2. Check direct mention in text with word boundaries
    for comp in vocab:
        parts = comp.lower().split(":")
        sub_name = parts[-1]
        pattern = rf"\b{re.escape(sub_name)}\b"
        if re.search(pattern, lower_text) or comp.lower() in lower_text:
            alternatives = [c for c in vocab if c != comp][:3]
            return comp, True, alternatives

    # 3. Fuzzy search if text contains candidate-like words (minimum length 4, strict cutoff)
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text)
    sub_names = [c.split(":")[-1] for c in vocab]
    for word in words:
        matches = difflib.get_close_matches(word, sub_names, n=1, cutoff=0.92)
        if matches:
            matched_sub = matches[0]
            for comp in vocab:
                if comp.endswith(matched_sub):
                    alternatives = [c for c in vocab if c != comp][:3]
                    return comp, True, alternatives

    return "General:Unknown", False, vocab[:3]
