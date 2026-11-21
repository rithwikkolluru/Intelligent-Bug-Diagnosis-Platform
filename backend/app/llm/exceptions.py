from __future__ import annotations


class LLMError(Exception):
    """Base exception for all LLM client failures."""

    def __init__(self, message: str, code: str = "LLM_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class LLMUnavailableError(LLMError):
    """Raised when the LLM provider cannot be reached, is unconfigured, or connection is refused."""

    def __init__(self, message: str = "LLM provider is unavailable or unconfigured"):
        super().__init__(message, code="LLM_UNAVAILABLE")


class LLMRateLimitError(LLMError):
    """Raised when rate limits (HTTP 429 or local request-per-minute threshold) are exceeded."""

    def __init__(self, message: str = "LLM rate limit exceeded"):
        super().__init__(message, code="LLM_RATE_LIMIT")


class LLMOutputError(LLMError):
    """Raised when LLM output cannot be parsed or validated against the expected schema after repair."""

    def __init__(self, message: str = "LLM output failed schema validation"):
        super().__init__(message, code="LLM_OUTPUT_ERROR")


class LLMTimeoutError(LLMError):
    """Raised when an LLM provider call exceeds the configured timeout threshold."""

    def __init__(self, message: str = "LLM call timed out"):
        super().__init__(message, code="LLM_TIMEOUT")
