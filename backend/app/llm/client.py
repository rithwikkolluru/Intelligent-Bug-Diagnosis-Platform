from __future__ import annotations

import json
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.llm.cache import LLMCache
from app.llm.exceptions import (
    LLMError,
    LLMOutputError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.llm.rate_limiter import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_GLOBAL_RATE_LIMITER: SlidingWindowRateLimiter | None = None


def get_shared_rate_limiter() -> SlidingWindowRateLimiter:
    global _GLOBAL_RATE_LIMITER
    if _GLOBAL_RATE_LIMITER is None:
        settings = get_settings()
        _GLOBAL_RATE_LIMITER = SlidingWindowRateLimiter(
            requests_per_minute=settings.LLM_REQUESTS_PER_MINUTE
        )
    return _GLOBAL_RATE_LIMITER


class LLMResponse(BaseModel, Generic[T]):
    data: T
    provider: str
    model: str
    latency_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cache_hit: bool = False
    attempts: int = 1


class LLMClient(ABC):
    """Abstract base class for all LLM providers supporting structured output generation."""

    def __init__(
        self,
        provider_name: str,
        default_model: str,
        timeout_s: float | None = None,
        max_retries: int | None = None,
        temperature: float | None = None,
        cache_dir: str | None = None,
        cache_enabled: bool | None = None,
    ):
        settings = get_settings()
        self.provider_name = provider_name
        self.default_model = default_model
        self.timeout_s = timeout_s if timeout_s is not None else settings.LLM_TIMEOUT_S
        self.max_retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        c_enabled = cache_enabled if cache_enabled is not None else settings.LLM_CACHE_ENABLED
        c_dir = cache_dir if cache_dir is not None else settings.LLM_CACHE_DIR
        self.cache = LLMCache(cache_dir=c_dir, enabled=c_enabled)
        self.rate_limiter = get_shared_rate_limiter()

    @abstractmethod
    def _call_raw_provider(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        temperature: float,
        max_tokens: int,
        json_schema: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        """Call the underlying LLM provider and return (raw_text_output, metadata)."""
        pass

    def _execute_with_retry(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        temperature: float,
        max_tokens: int,
        json_schema: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any], int]:
        attempts = 0
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            attempts = attempt
            try:
                # 1. Enforce local request rate limit
                self.rate_limiter.acquire(timeout_s=5.0)

                # 2. Call provider
                raw_text, meta = self._call_raw_provider(
                    system_prompt, user_content, model, temperature, max_tokens, json_schema
                )
                return raw_text, meta, attempts

            except LLMRateLimitError as exc:
                last_error = exc
                if attempt == self.max_retries:
                    raise
                backoff = (2**attempt) + random.uniform(0.1, 0.5)
                logger.warning(
                    "Rate limit encountered on attempt %d/%d. Backing off for %.2fs...",
                    attempt,
                    self.max_retries,
                    backoff,
                )
                time.sleep(backoff)

            except (LLMTimeoutError, httpx.TimeoutException) as exc:
                last_error = LLMTimeoutError(f"Call timed out after {self.timeout_s}s: {exc}")
                if attempt == self.max_retries:
                    raise last_error from exc
                backoff = (1.5**attempt) + random.uniform(0.1, 0.4)
                logger.warning("Timeout on attempt %d/%d. Retrying in %.2fs...", attempt, self.max_retries, backoff)
                time.sleep(backoff)

            except LLMUnavailableError:
                raise

            except Exception as exc:
                last_error = exc
                if attempt == self.max_retries:
                    raise LLMError(f"LLM request failed after {self.max_retries} attempts: {exc}") from exc
                backoff = (1.5**attempt) + random.uniform(0.1, 0.3)
                logger.warning("Error on attempt %d/%d (%s). Retrying...", attempt, self.max_retries, exc)
                time.sleep(backoff)

        raise LLMError(f"Failed to get response after {self.max_retries} attempts: {last_error}")

    def generate_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_model: type[T],
        *,
        model: str | None = None,
        prompt_version: str = "v1",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse[T]:
        settings = get_settings()
        chosen_model = model or settings.LLM_MODEL or self.default_model
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_OUTPUT_TOKENS
        schema = response_model.model_json_schema()

        # 1. Check disk cache
        cache_key = self.cache.compute_key(
            self.provider_name, chosen_model, prompt_version, system_prompt, user_content, temp
        )
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            try:
                parsed = response_model.model_validate(cached_data)
                return LLMResponse(
                    data=parsed,
                    provider=self.provider_name,
                    model=chosen_model,
                    latency_ms=0.0,
                    cache_hit=True,
                    attempts=1,
                )
            except ValidationError:
                pass  # Schema updated; re-generate

        # 2. Call provider with retries
        start_t = time.perf_counter()
        raw_text, meta, attempts = self._execute_with_retry(
            system_prompt, user_content, chosen_model, temp, tokens, schema
        )
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        # 3. Clean and parse JSON
        parsed_obj: T | None = None
        parse_err: str | None = None

        try:
            cleaned_text = self._strip_fences(raw_text)
            data_dict = json.loads(cleaned_text)
            parsed_obj = response_model.model_validate(data_dict)
        except (json.JSONDecodeError, ValidationError) as exc:
            parse_err = str(exc)

        # 4. Exactly ONE repair attempt on schema / parse error
        if parsed_obj is None:
            logger.info("Output failed validation (%s). Initiating 1 repair attempt...", parse_err)
            repair_prompt = (
                f"Your previous response failed JSON/schema validation with the following error:\n{parse_err}\n\n"
                f"Previous output was:\n{raw_text[:1000]}\n\n"
                f"Please fix and output ONLY a valid JSON object strictly complying with this schema:\n"
                f"{json.dumps(schema)}"
            )
            repair_text, _, repair_attempts = self._execute_with_retry(
                system_prompt, repair_prompt, chosen_model, temp, tokens, schema
            )
            attempts += repair_attempts

            try:
                cleaned_repair = self._strip_fences(repair_text)
                repaired_dict = json.loads(cleaned_repair)
                parsed_obj = response_model.model_validate(repaired_dict)
            except Exception as final_exc:
                raise LLMOutputError(
                    f"LLM output could not be parsed into {response_model.__name__} after repair attempt: {final_exc}"
                ) from final_exc

        # 5. Save to disk cache
        self.cache.set(cache_key, parsed_obj.model_dump(), self.provider_name, chosen_model)

        return LLMResponse(
            data=parsed_obj,
            provider=self.provider_name,
            model=chosen_model,
            latency_ms=elapsed_ms,
            prompt_tokens=meta.get("prompt_tokens"),
            completion_tokens=meta.get("completion_tokens"),
            cache_hit=False,
            attempts=attempts,
        )

    @staticmethod
    def _strip_fences(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text


class GeminiClient(LLMClient):
    """Google Gemini client using native REST API with strict JSON schema support."""

    def __init__(self, **kwargs):
        super().__init__(provider_name="gemini", default_model="gemini-2.5-flash", **kwargs)

    def _call_raw_provider(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        temperature: float,
        max_tokens: int,
        json_schema: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        settings = get_settings()
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise LLMUnavailableError("GEMINI_API_KEY is not configured.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key.strip()}"
        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\n{user_content}"}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 429:
                    raise LLMRateLimitError(f"Gemini API rate limit exceeded (HTTP 429): {resp.text}")
                if resp.status_code != 200:
                    raise LLMError(f"Gemini API error (HTTP {resp.status_code}): {resp.text}")

                body = resp.json()
                candidates = body.get("candidates", [])
                if not candidates:
                    raise LLMOutputError("Gemini returned empty candidates.")

                raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                usage = body.get("usageMetadata", {})
                return raw_text, {
                    "prompt_tokens": usage.get("promptTokenCount"),
                    "completion_tokens": usage.get("candidatesTokenCount"),
                }
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Gemini call timed out after {self.timeout_s}s") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise LLMUnavailableError(f"Cannot connect to Gemini API: {exc}") from exc


class GroqClient(LLMClient):
    """Groq client using official OpenAI-compatible endpoint with JSON object mode."""

    def __init__(self, **kwargs):
        super().__init__(provider_name="groq", default_model="llama-3.3-70b-versatile", **kwargs)

    def _call_raw_provider(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        temperature: float,
        max_tokens: int,
        json_schema: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        settings = get_settings()
        api_key = settings.GROQ_API_KEY
        if not api_key:
            raise LLMUnavailableError("GROQ_API_KEY is not configured.")

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    raise LLMRateLimitError(f"Groq rate limit exceeded (HTTP 429): {resp.text}")
                if resp.status_code != 200:
                    raise LLMError(f"Groq API error (HTTP {resp.status_code}): {resp.text}")

                body = resp.json()
                choice = body.get("choices", [{}])[0]
                raw_text = choice.get("message", {}).get("content", "")
                usage = body.get("usage", {})
                return raw_text, {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                }
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Groq call timed out after {self.timeout_s}s") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise LLMUnavailableError(f"Cannot connect to Groq endpoint: {exc}") from exc


class OllamaClient(LLMClient):
    """Local Ollama client using REST API with JSON format mode."""

    def __init__(self, **kwargs):
        settings = get_settings()
        super().__init__(provider_name="ollama", default_model=settings.LLM_MODEL or "llama3.2", **kwargs)

    def _call_raw_provider(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        temperature: float,
        max_tokens: int,
        json_schema: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        settings = get_settings()
        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        url = f"{base_url}/api/chat"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                resp = client.post(url, json=payload)
                if resp.status_code != 200:
                    raise LLMError(f"Ollama error (HTTP {resp.status_code}): {resp.text}")

                body = resp.json()
                raw_text = body.get("message", {}).get("content", "")
                return raw_text, {
                    "prompt_tokens": body.get("prompt_eval_count"),
                    "completion_tokens": body.get("eval_count"),
                }
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Ollama call timed out after {self.timeout_s}s") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise LLMUnavailableError(f"Cannot connect to local Ollama at {base_url}: {exc}") from exc


class FakeLLMClient(LLMClient):
    """Scriptable in-memory fake client for deterministic testing."""

    def __init__(
        self,
        canned_responses: list[Any] | None = None,
        raise_rate_limit_count: int = 0,
        raise_timeout_count: int = 0,
        raise_unavailable: bool = False,
        **kwargs,
    ):
        cache_enabled = kwargs.pop("cache_enabled", False)
        super().__init__(
            provider_name="fake",
            default_model="fake-v1",
            cache_enabled=cache_enabled,
            **kwargs,
        )
        self.canned_responses = list(canned_responses or [])
        self.calls: list[dict[str, Any]] = []
        self._rate_limit_countdown = raise_rate_limit_count
        self._timeout_countdown = raise_timeout_count
        self.raise_unavailable = raise_unavailable

    def _call_raw_provider(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        temperature: float,
        max_tokens: int,
        json_schema: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        self.calls.append({
            "system_prompt": system_prompt,
            "user_content": user_content,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "json_schema": json_schema,
        })

        if self.raise_unavailable:
            raise LLMUnavailableError("Simulated LLM service unavailable.")

        if self._rate_limit_countdown > 0:
            self._rate_limit_countdown -= 1
            raise LLMRateLimitError("Simulated HTTP 429 Rate Limit")

        if self._timeout_countdown > 0:
            self._timeout_countdown -= 1
            raise LLMTimeoutError("Simulated timeout error")

        if self.canned_responses:
            next_resp = self.canned_responses.pop(0)
            if isinstance(next_resp, BaseModel):
                return next_resp.model_dump_json(), {"prompt_tokens": 50, "completion_tokens": 50}
            if isinstance(next_resp, dict):
                return json.dumps(next_resp), {"prompt_tokens": 50, "completion_tokens": 50}
            return str(next_resp), {"prompt_tokens": 50, "completion_tokens": 50}

        # Default minimal valid response
        return "{}", {"prompt_tokens": 10, "completion_tokens": 10}


def get_llm_client(provider: str | None = None) -> LLMClient:
    """Factory selecting the active LLM client based on environment or explicit parameter."""
    settings = get_settings()
    p = (provider or settings.LLM_PROVIDER or "none").lower().strip()

    if p == "gemini":
        return GeminiClient()
    if p == "groq":
        return GroqClient()
    if p == "ollama":
        return OllamaClient()
    if p == "fake":
        return FakeLLMClient()
    if p in {"none", ""}:
        return FakeLLMClient(raise_unavailable=True)

    raise ValueError(f"Unsupported LLM_PROVIDER: '{p}'. Must be one of: groq, gemini, ollama, fake, none.")
