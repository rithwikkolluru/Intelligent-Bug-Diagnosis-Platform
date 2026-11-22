# LLM Abstraction Layer — Design and Reference

**Module:** `backend/app/llm/`  
**Entry point:** `app/llm/client.py` → `get_llm_client()`  
**Tests:** `tests/test_llm_layer.py` (12 tests)

---

## Design Goals

1. **Single interface** — agents call `client.complete(prompt)` regardless of which provider is configured.
2. **Graceful degradation** — when no LLM is configured or the provider is down, `LLMUnavailableError` is raised and agents fall back to rule-based logic.
3. **Free and local only** — Groq (free tier), Gemini (free tier), Ollama (local). No paid services hard-coded.
4. **Model names are configurable** — never hard-coded. All set via environment variables.
5. **Caching** — disk-based response cache to avoid redundant API calls during validation runs.
6. **Rate limiting** — built-in token-bucket throttle respects `LLM_REQUESTS_PER_MINUTE`.
7. **Retries** — exponential back-off with jitter up to `LLM_MAX_RETRIES`.

---

## Architecture

```
Agent code
    │
    ▼  get_llm_client()
LLMClient  (abstract)
    ├── GroqLLMClient      (app/llm/groq_client.py)
    ├── GeminiLLMClient    (app/llm/gemini_client.py)
    ├── OllamaLLMClient    (app/llm/ollama_client.py)
    └── FakeLLMClient      (app/llm/fake_client.py)  ← tests only

LLMClient.complete(prompt: str) → str   # raw response text
LLMClient.complete_structured(prompt, schema) → dict   # validates JSON
```

---

## Provider Selection

Set `LLM_PROVIDER` to one of:

| Value | Provider | Requires |
|---|---|---|
| `none` | Disabled — `LLMUnavailableError` always raised | Nothing |
| `groq` | Groq Cloud API | `GROQ_API_KEY` |
| `gemini` | Google Gemini API | `GEMINI_API_KEY` |
| `ollama` | Local Ollama server | Ollama running at `OLLAMA_BASE_URL` |
| `fake` | In-memory test stub | Used in tests only |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `none` | Active provider. System works fully without one (rule-based mode). |
| `LLM_MODEL` | (provider default) | Model name. **You must verify free-tier availability.** |
| `GROQ_API_KEY` | — | Groq API key. Never commit. |
| `GEMINI_API_KEY` | — | Gemini API key. Never commit. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL. |
| `LLM_TIMEOUT_S` | `30.0` | Per-request timeout in seconds. |
| `LLM_MAX_RETRIES` | `3` | Max retry attempts on transient errors. |
| `LLM_TEMPERATURE` | `0.0` | Sampling temperature. Keep at 0 for deterministic outputs. |
| `LLM_MAX_OUTPUT_TOKENS` | `2048` | Maximum tokens in LLM response. |
| `LLM_CACHE_DIR` | `.llm_cache` | Directory for disk-based response cache. |
| `LLM_CACHE_ENABLED` | `true` | Set to `false` to disable caching (e.g. during development). |
| `LLM_REQUESTS_PER_MINUTE` | `30` | Rate limit for API calls. Free tiers may require lowering. |

---

## Caching

LLM responses are cached by prompt SHA-256 hash in `{LLM_CACHE_DIR}/{provider}/{model}/`. Cache entries are persistent across runs. This is essential for validation runs that call the LLM hundreds of times.

```bash
# Clear cache if prompts change
rm -rf .llm_cache/
```

---

## Retry and Rate-Limit Behaviour

- Transient HTTP errors (429, 503, timeouts) trigger exponential back-off: `2^attempt * (0.5–1.5 jitter)` seconds.
- Rate-limit throttle is a token-bucket with `LLM_REQUESTS_PER_MINUTE` tokens, refilled per minute.
- After `LLM_MAX_RETRIES` failures, `LLMUnavailableError` is raised and the agent falls back to rules.

---

## Prompt Registry

**Module:** `app/agents/prompt_registry.py`  
**Prompt files:** `backend/prompts/`

Prompts are loaded from text files at module import time. The registry maps `(agent_name, version)` → prompt template string. Agents reference prompts by name and version for reproducibility.

```python
from app.agents.prompt_registry import get_prompt_registry
registry = get_prompt_registry()
prompt = registry.get("triage_classify", "v1")
```

Prompt files are plain text. Variable substitution uses `{variable}` placeholders.

---

## FakeLLMClient (Tests)

`FakeLLMClient` accepts a `canned_responses` dict mapping prompt substrings to response strings. Use it in tests to avoid real API calls:

```python
from app.llm.fake_client import FakeLLMClient

client = FakeLLMClient(canned_responses={
    "classify": '{"severity": "High", "priority": "P2", ...}',
})
agent = TriageAgent(llm_client=client)
```

---

## Usage Guidance for Validation Runs

Validation runs (M2.4) may call the LLM 50–200 times. To avoid exceeding free-tier limits:

1. **Always enable caching** (`LLM_CACHE_ENABLED=true`) — repeated runs cost nothing.
2. **Lower rate limit** if on a 30 req/min free tier: `LLM_REQUESTS_PER_MINUTE=20`.
3. **Use `--dry-run`** mode on the validation CLI to estimate call count before running.
4. **Use Groq** for the fastest free-tier responses; Ollama for unlimited local runs.
5. Runs that estimate >30 minutes will warn you before starting.

---

## What to Verify Before Use

> **Groq free tier**: Check https://console.groq.com/settings/limits — rate limits vary by model. `llama-3.1-8b-instant` has generous limits.

> **Gemini free tier**: Check https://ai.google.dev/pricing — `gemini-2.5-flash` free tier has 15 req/min. Set `LLM_REQUESTS_PER_MINUTE=12` to stay safe.

> **Ollama**: Models are downloaded once and stored locally. Run `ollama pull llama3.2` before first use.
