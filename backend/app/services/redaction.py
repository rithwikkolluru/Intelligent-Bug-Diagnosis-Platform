from __future__ import annotations

import re


def redact_secrets(text: str) -> tuple[str, int]:
    if not text:
        return text, 0

    cleaned = text
    count = 0

    patterns = [
        (re.compile(r'(?is)(["\']?(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)["\']?\s*[:=]\s*["\']?)([^"\'\s,}\]]+)'), 'pair'),
        (re.compile(r'(?i)(authorization)\s*:\s*bearer\s+([A-Za-z0-9._~+/=-]+)'), 'bearer'),
        (re.compile(r'(?i)(aws_access_key_id|aws_access_key|access_key_id)\s*[:=]\s*([A-Z0-9]{16,})'), 'aws'),
        (re.compile(r'(?i)(?:\b(?:postgres|mysql|mongodb|redis|amqp|postgresql|mssql)://)([^:@/\s]+):([^@\s/]+)@([^\s]+)'), 'connection'),
        (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----', re.DOTALL | re.IGNORECASE), 'private_key'),
    ]

    for pattern, kind in patterns:
        if kind == 'private_key':
            cleaned, n = re.subn(pattern, '[REDACTED]', cleaned)
            count += n
            continue
        if kind == 'bearer':
            cleaned, n = re.subn(pattern, r'\1: Bearer [REDACTED]', cleaned)
            count += n
            continue
        if kind == 'aws':
            cleaned, n = re.subn(pattern, r'\1: [REDACTED]', cleaned)
            count += n
            continue
        if kind == 'connection':
            cleaned, n = re.subn(pattern, lambda m: f"{m.group(1)}:[REDACTED]@{m.group(3)}", cleaned)
            count += n
            continue
        cleaned, n = re.subn(pattern, lambda m: f"{m.group(1)}[REDACTED]", cleaned)
        count += n

    cleaned, n = re.subn(
        r'(?is)((?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|authorization)\s*[:=]\s*["\']?)([A-Fa-f0-9]{24,}|[A-Za-z0-9+/=]{32,})(?=[\s"\'\,}\]])',
        lambda m: f"{m.group(1)}[REDACTED]",
        cleaned,
    )
    count += n

    return cleaned, count
