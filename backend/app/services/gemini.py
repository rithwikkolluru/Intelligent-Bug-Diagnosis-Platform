from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.bug import BugReport
from app.rag.smoke_search import search

logger = logging.getLogger(__name__)


def retrieve_relevant_historical_defects(bug: BugReport, top_k: int = 3) -> list[dict[str, Any]]:
    """Retrieve semantically similar historical defects from ChromaDB RAG store."""
    query_text = f"{bug.title} {bug.programming_language or ''}\n{bug.description[:300]}"
    if bug.stack_trace:
        first_line = bug.stack_trace.strip().split("\n")[0]
        query_text = f"{first_line}\n{query_text}"

    try:
        raw_hits = search(query_text=query_text, k=top_k)
    except Exception as exc:
        logger.warning("RAG retrieval failed: %s", exc)
        raw_hits = []

    unique_defects: dict[str, dict[str, Any]] = {}
    for hit in raw_hits:
        meta = hit.get("metadata") or {}
        chunk_id = hit.get("chunk_id") or ""
        defect_id = meta.get("defect_id") or (chunk_id.split("::")[0] if "::" in chunk_id else chunk_id) or "DEF-UNKNOWN"
        if defect_id in unique_defects:
            continue

        raw_title = meta.get("summary") or meta.get("title")
        if not raw_title:
            first_line = hit.get("text", "").split("\n")[0].strip()
            raw_title = first_line[:120] if first_line else f"Historical defect {defect_id}"

        project = meta.get("project") or "open-source"
        resolution = meta.get("resolution") or "fixed"
        source_url = meta.get("source_url") or f"https://bugs.{project}.org/show_bug.cgi?id={defect_id}"

        unique_defects[defect_id] = {
            "defect_id": str(defect_id),
            "title": str(raw_title),
            "project": str(project),
            "similarity": float(hit.get("similarity", 0.75)),
            "resolution": str(resolution),
            "source_url": str(source_url),
            "snippet": str(hit.get("text", "")[:200]),
        }

    return list(unique_defects.values())[:top_k]


def _fallback_heuristic_diagnose(bug: BugReport, similar_defects: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate high-quality diagnostic analysis using heuristic rule-based engine when Gemini API key is absent."""
    content = f"{bug.title} {bug.description} {bug.stack_trace or ''} {bug.error_logs or ''}".lower()
    lang = (bug.programming_language or "General").capitalize()

    # Pattern matches
    if "nullpointer" in content or "null pointer" in content or "nonetype" in content or "cannot read properties of undefined" in content or "cannot read property" in content:
        root_cause = (
            f"Null Reference Dereference: The application attempted to access a member or method on an uninitialized "
            f"or null reference in {lang}. In distributed workflows or async calls, this typically occurs when an entity lookup, "
            f"deserialization step, or authentication context returns null/None without an upstream defensive guard."
        )
        if "python" in lang.lower():
            code_patch = (
                "# Solution: Add defensive guard or optional chaining\n"
                "# Before:\n"
                "# value = response['data']['user_id']\n\n"
                "# After:\n"
                "if response and response.get('data'):\n"
                "    value = response['data'].get('user_id')\n"
                "else:\n"
                "    logger.warning('Payload data is missing')\n"
                "    value = None"
            )
        elif "javascript" in lang.lower():
            code_patch = (
                "// Solution: Use optional chaining (?.) and default fallback\n"
                "// Before:\n"
                "// const userId = payload.data.user.id;\n\n"
                "// After:\n"
                "const userId = payload?.data?.user?.id ?? null;\n"
                "if (!userId) {\n"
                "  console.warn('User ID missing from payload');\n"
                "}"
            )
        else:
            code_patch = (
                "// Solution: Introduce Optional or Objects.requireNonNull guard\n"
                "// Before:\n"
                "// String userId = user.getId();\n\n"
                "// After:\n"
                "if (user == null || user.getId() == null) {\n"
                "    logger.warn(\"User context is null during request processing\");\n"
                "    throw new IllegalArgumentException(\"User must not be null\");\n"
                "}\n"
                "String userId = user.getId();"
            )
        fix_recommendation = (
            "1. Implement defensive checks at the boundary layer before accessing object attributes.\n"
            "2. Utilize null-safe operators (e.g., Optional in Java, optional chaining in JS, or .get() with defaults in Python).\n"
            "3. Add unit test assertions simulating missing or null inputs."
        )
        verification_steps = [
            "Write a unit test providing null or undefined input to verify graceful handling without unhandled exceptions.",
            "Verify that logger captures a warning rather than crashing the request worker.",
            "Test valid payload to ensure standard execution path remains unaltered.",
        ]
        confidence = 0.92

    elif "index" in content or "bounds" in content or "out of range" in content:
        root_cause = (
            f"Index Out Of Bounds Exception: An array, list, or slice index exceeded the actual length of the collection "
            f"during iteration or direct index access in {lang}."
        )
        code_patch = (
            "# Solution: Validate collection size prior to index access\n"
            "if index >= 0 and index < len(items):\n"
            "    target = items[index]\n"
            "else:\n"
            "    raise IndexError(f'Index {index} out of bounds for collection of size {len(items)}')"
        )
        fix_recommendation = (
            "1. Validate collection boundaries before direct indexing.\n"
            "2. Use iterator constructs (for-each / enumerate) instead of manual index offsets where possible.\n"
            "3. Handle empty collection edge cases explicitly."
        )
        verification_steps = [
            "Test boundary conditions: index 0 on empty list, index == len, and negative indices.",
            "Run regression tests across batch parser functions.",
        ]
        confidence = 0.88

    elif "timeout" in content or "connection" in content or "refused" in content:
        root_cause = (
            f"Network / Resource Timeout: Communication with an upstream dependency timed out or was refused. "
            f"This is commonly caused by missing socket timeout limits, unhandled connection pool exhaustion, or downstream latency."
        )
        code_patch = (
            "# Solution: Configure explicit timeouts with retry backoff\n"
            "import httpx\n"
            "from tenacity import retry, stop_after_attempt, wait_exponential\n\n"
            "@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))\n"
            "async def fetch_with_timeout(url: str):\n"
            "    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:\n"
            "        response = await client.get(url)\n"
            "        response.raise_for_status()\n"
            "        return response.json()"
        )
        fix_recommendation = (
            "1. Establish explicit connection and read timeouts on all external network clients.\n"
            "2. Implement exponential backoff and jitter on idempotent operations.\n"
            "3. Add a circuit breaker pattern to fail fast when external services degrade."
        )
        verification_steps = [
            "Simulate connection latency and ensure timeout interrupts cleanly within configured limit.",
            "Verify retry logic activates up to max attempts with exponential backoff.",
        ]
        confidence = 0.87

    else:
        root_cause = (
            f"Execution Logic Failure: Analysis of the error trace indicates an unhandled runtime exception in {lang}. "
            f"The fault originated in the component '{bug.title}' during input processing or state transition."
        )
        code_patch = (
            "# Solution: Wrap high-risk block with targeted exception handling\n"
            "try:\n"
            "    process_record(payload)\n"
            "except (ValueError, KeyError) as err:\n"
            "    logger.error('Invalid payload data: %s', err, exc_info=True)\n"
            "    handle_recovery(payload)"
        )
        fix_recommendation = (
            "1. Inspect stack trace frames to isolate the exact line throwing the exception.\n"
            "2. Wrap the failing logic with specific exception handling and logging.\n"
            "3. Cross-reference similar historical defects to see previous patch strategies."
        )
        verification_steps = [
            "Reproduce with the exact error payload and assert error is captured gracefully.",
            "Run test suite to confirm no regressions.",
        ]
        confidence = 0.82

    duplicate_assessment = (
        f"Compared against {len(similar_defects)} historical open-source defects. "
        + (f"Found semantic similarities with {similar_defects[0]['defect_id']} ({similar_defects[0]['title']})." if similar_defects else "No direct duplicate found in historical repository.")
    )

    return {
        "root_cause": root_cause,
        "fix_recommendation": fix_recommendation,
        "code_patch": code_patch,
        "verification_steps": verification_steps,
        "similar_defects": similar_defects,
        "duplicate_assessment": duplicate_assessment,
        "confidence_score": confidence,
        "model_used": "Heuristic Engine (Provide GEMINI_API_KEY in .env or settings for Gemini AI)",
    }


def _normalize_text_field(val: Any, default: str = "") -> str:
    if val is None:
        return default
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        return "\n\n".join(str(item).strip() for item in val if str(item).strip())
    if isinstance(val, dict):
        return "\n".join(f"{k}: {v}" for k, v in val.items())
    return str(val).strip()


def _normalize_list_field(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(item).strip() for item in val if str(item).strip()]
    if isinstance(val, str):
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed]
            except Exception:
                pass
        return [line.strip() for line in val.split("\n") if line.strip()]
    return [str(val).strip()]


def _clean_and_parse_json(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        return json.loads(text, strict=False)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0), strict=False)
        raise


async def diagnose_bug_with_gemini(bug: BugReport, api_key_override: str | None = None) -> dict[str, Any]:
    """Diagnose bug using Gemini API if key is available, else fallback smoothly."""
    settings = get_settings()
    api_key = api_key_override or settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")

    # 1. Retrieve RAG evidence
    similar_defects = retrieve_relevant_historical_defects(bug, top_k=3)

    # 2. If no API key configured, use intelligent heuristic fallback
    if not api_key or not api_key.strip():
        logger.info("GEMINI_API_KEY not configured. Using Heuristic Engine fallback.")
        return _fallback_heuristic_diagnose(bug, similar_defects)

    # 3. Call Google Gemini API
    gemini_model = settings.GEMINI_MODEL or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key.strip()}"

    system_instruction = (
        "You are an elite Principal Software Engineer and automated bug diagnosis specialist. "
        "Analyze the provided software bug report, stack trace, error logs, and retrieved historical defect evidence. "
        "Output ONLY a valid JSON object matching the required schema with concrete, evidence-backed fixes."
    )

    evidence_str = "\n".join([
        f"- Defect [{d['defect_id']}] ({d['project']}): {d['title']} | Resolution: {d['resolution']} (Similarity: {d['similarity']})"
        for d in similar_defects
    ]) if similar_defects else "No previous similar defects found in vector store."

    user_prompt = f"""
Bug Report Details:
- Title: {bug.title}
- Programming Language: {bug.programming_language or 'Unknown / Auto'}
- Description: {bug.description}
- Stack Trace:
{bug.stack_trace or 'None'}
- Error Logs:
{bug.error_logs or 'None'}

Retrieved Historical Evidence (from Mozilla/Eclipse/Apache defect database):
{evidence_str}

Please generate an expert diagnosis in strict JSON format with the following keys:
1. "root_cause": (Detailed explanation of why this bug occurs based on trace and logs)
2. "fix_recommendation": (Numbered step-by-step guidance on how to fix this bug)
3. "code_patch": (Executable code snippet demonstrating the fix, with before and after comments)
4. "verification_steps": (Array of strings representing test cases or verification steps to prove the fix)
5. "duplicate_assessment": (Evaluation of whether this matches past defects and duplicate risk)
6. "confidence_score": (Float between 0.0 and 1.0 indicating diagnosis certainty)
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{system_instruction}\n\n{user_prompt}"}],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
            "maxOutputTokens": 4096,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                logger.error("Gemini API returned error: %s - %s", response.status_code, response.text)
                fallback = _fallback_heuristic_diagnose(bug, similar_defects)
                fallback["model_used"] = f"Heuristic Fallback (Gemini API HTTP {response.status_code})"
                return fallback

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                logger.warning("Gemini returned empty candidates. Falling back.")
                return _fallback_heuristic_diagnose(bug, similar_defects)

            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            parsed = _clean_and_parse_json(raw_text)

            return {
                "root_cause": _normalize_text_field(parsed.get("root_cause"), "Root cause identified by Gemini."),
                "fix_recommendation": _normalize_text_field(parsed.get("fix_recommendation"), "Review code fix recommendations."),
                "code_patch": _normalize_text_field(parsed.get("code_patch"), ""),
                "verification_steps": _normalize_list_field(parsed.get("verification_steps")),
                "similar_defects": similar_defects,
                "duplicate_assessment": _normalize_text_field(parsed.get("duplicate_assessment"), "No direct duplicate identified."),
                "confidence_score": float(parsed.get("confidence_score") or 0.90),
                "model_used": f"Google Gemini ({gemini_model})",
            }
    except Exception as exc:
        logger.exception("Error while communicating with Gemini API: %s", exc)
        fallback = _fallback_heuristic_diagnose(bug, similar_defects)
        fallback["model_used"] = f"Heuristic Fallback ({exc.__class__.__name__})"
        return fallback
