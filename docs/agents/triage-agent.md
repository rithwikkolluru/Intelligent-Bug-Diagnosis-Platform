# Triage Agent — Design and Reference

**Module:** `backend/app/agents/triage/`  
**Agent name:** `"triage"`  
**Prompt version:** `v1`  
**Output schema:** `TriageResult` (`app/agents/triage/schemas.py`)

---

## Responsibilities

The Triage Agent classifies a bug report into four dimensions:

| Dimension | Output | Values |
|---|---|---|
| **Severity** | `Severity` enum | `Critical`, `High`, `Medium`, `Low` |
| **Priority** | `Priority` enum | `P1`, `P2`, `P3`, `P4` |
| **Component** | `ComponentInfo` | canonical name + matched namespace + confidence |
| **Confidence** | `ConfidenceBreakdown` | per-dimension 0.0–1.0, overall |

It also produces a short `reasoning` string explaining the decision.

---

## Architecture — Two-Stage Pipeline

```
AgentInput
    │
    ▼
[1] Rule Baseline (deterministic, always runs first)
    │  ─ keyword/pattern scanning
    │  ─ component vocabulary matching
    │  ─ severity/priority heuristics
    │
    ▼
[2] LLM Classifier (optional, structured JSON output)
    │  ─ prompt from registry (triage_classify_v1)
    │  ─ Groq / Gemini / Ollama behind LLMClient
    │  ─ Pydantic validation of output
    │  ─ Falls back to rule baseline if LLM unavailable or response invalid
    │
    ▼
TriageResult
```

The rule baseline always runs first. If no LLM is configured (`LLM_PROVIDER=none`) or if the LLM call fails after retries, the rule-baseline result is returned directly — the system is fully functional in offline/degraded mode.

---

## Schemas

### TriageResult

```python
class TriageResult(BaseModel):
    severity: Severity              # Critical | High | Medium | Low
    priority: Priority              # P1 | P2 | P3 | P4
    component: ComponentInfo        # canonical name from vocabulary
    confidence: float               # 0.0–1.0 overall
    confidence_breakdown: ConfidenceBreakdown
    reasoning: str                  # max ~200 chars
    method: str                     # "rule" | "llm" | "hybrid"
    prompt_version: str | None
```

### Severity — Rubric

| Level | Criteria |
|---|---|
| **Critical** | Data loss, security breach, crash/hang, production down, blocker regression |
| **High** | Major feature broken, significant performance degradation, no workaround |
| **Medium** | Feature partially broken, workaround exists, affects subset of users |
| **Low** | Cosmetic, documentation, enhancement, minor annoyance |

### Priority — Rubric (P1–P4)

| Priority | Trigger criteria |
|---|---|
| **P1** | Critical severity OR security/data-loss risk OR release blocker; immediate action |
| **P2** | High severity; significant user impact; fix before next release |
| **P3** | Medium severity; fix in normal sprint cycle |
| **P4** | Low severity; backlog; cosmetic or enhancement |

### Component Vocabulary

The vocabulary is defined in `app/agents/triage/vocabulary.py`. It is built from the top-30 historical components across Mozilla Firefox, Apache, and Eclipse projects.

| Strategy | Detail |
|---|---|
| Namespace matching | Java/Python/JS package prefixes → component (e.g. `org.apache.http` → `HTTP Client`) |
| Keyword matching | Keyword sets per component (e.g. `{"null", "npe", "nullpointer"}` → `Core`) |
| Fuzzy matching | `difflib.SequenceMatcher` with cutoff 0.92 for display text matching |
| Fallback | `ComponentInfo(name="Unknown", confidence=0.0)` |

---

## Rule Baseline Details (`app/agents/triage/rules.py`)

Deterministic heuristics — no LLM required:

1. **Severity signals**: keyword lists per severity level scanned across title + description + stack trace.
2. **Priority derivation**: priority is derived from severity with additional boosts for security/data-loss keywords, regression markers, and "release" blocking terms.
3. **Component detection**: `match_component(text)` tries namespace matching first, then keyword matching, then fuzzy matching.
4. **Confidence scoring**: keyword hit density, explicit security/crash markers, and component match quality all contribute to per-dimension confidence.

---

## LLM Prompt (`prompts/triage_classify_v1.txt`)

The prompt instructs the LLM to:
- Output strict JSON matching the `TriageResult` schema
- Use the rubric above for severity/priority decisions
- Identify the most likely component from the vocabulary
- Provide a reasoning string under 200 characters

### Environment Variables Controlling LLM Behaviour

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `none` | `groq` \| `gemini` \| `ollama` \| `fake` \| `none` |
| `LLM_MODEL` | (provider default) | Model name — verify free-tier availability before use |
| `LLM_TEMPERATURE` | `0.0` | Keep at 0 for deterministic triage |
| `LLM_MAX_OUTPUT_TOKENS` | `2048` | Triage output is small; 512 is sufficient |
| `LLM_CACHE_ENABLED` | `true` | Cache LLM responses to avoid redundant calls |
| `TRIAGE_USE_RETRIEVAL` | `false` | Enable retrieval-informed nearest-neighbour agreement |
| `TRIAGE_TOP_K_NEIGHBOURS` | `3` | Number of similar historical bugs to retrieve |

---

## Running the Triage Agent

### Via CLI

```bash
# Rule-only (no LLM needed)
cd /path/to/project
PYTHONPATH=backend python -m app.agents.run \
  --agent triage \
  --text "NullPointerException on startup when loading user config" \
  --no-llm

# With a stack trace file
PYTHONPATH=backend python -m app.agents.run \
  --agent triage \
  --file data/samples/agents/java_crash.txt

# Both agents
PYTHONPATH=backend python -m app.agents.run \
  --agent both \
  --text "Production database deadlock" \
  --stack-trace "java.lang.RuntimeException: deadlock"
```

### Via Python API

```python
from app.agents.base import AgentInput
from app.agents.triage.agent import TriageAgent

agent = TriageAgent()
result = agent.run(AgentInput(
    title="NullPointerException on startup",
    description="The application crashes on startup when loading user preferences.",
    stack_trace="java.lang.NullPointerException\n  at com.example.App.load(App.java:42)",
))
print(result.output.severity)      # Severity.High
print(result.output.priority)      # Priority.P2
print(result.output.component.name)
print(result.output.reasoning)
```

---

## Tests

Test file: `tests/test_triage_agent.py` (14 tests)

Coverage:
- Rule-only severity classification (critical, high, medium, low)
- Security → P1 priority override
- Regression → priority boost
- Component detection (Java namespace, keyword, fuzzy, unknown)
- FakeLLM structured output acceptance and fallback
- LLM failure → rule fallback
- JSON round-trip of `TriageResult`
- Empty input produces valid Low/P4 output

Run:
```bash
cd backend && PYTHONPATH=. pytest ../tests/test_triage_agent.py -v
```

---

## What to Verify Before Enabling LLM

> **Groq**: Visit https://console.groq.com — confirm your chosen model (e.g. `llama-3.1-8b-instant`) is available on the free tier. Set `LLM_PROVIDER=groq`, `LLM_MODEL=llama-3.1-8b-instant`, `GROQ_API_KEY=<key>`.

> **Gemini**: Visit https://ai.google.dev — confirm `gemini-2.5-flash` free tier quota. Set `LLM_PROVIDER=gemini`, `LLM_MODEL=gemini-2.5-flash`, `GEMINI_API_KEY=<key>`.

> **Ollama**: Run `ollama pull llama3.2` locally. Set `LLM_PROVIDER=ollama`, `LLM_MODEL=llama3.2`, `OLLAMA_BASE_URL=http://localhost:11434`.
