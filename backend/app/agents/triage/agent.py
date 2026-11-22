from __future__ import annotations

import logging
import time

from app.agents.base import AgentInput, AgentResult, BaseAgent, sanitize_and_prepare_content
from app.agents.prompt_registry import get_prompt_registry
from app.agents.triage.rules import evaluate_rule_baseline
from app.agents.triage.schemas import TriageResult
from app.agents.triage.vocabulary import ALL_KNOWN_COMPONENTS
from app.core.config import settings
from app.llm.client import LLMClient, get_llm_client
from app.llm.exceptions import LLMUnavailableError

logger = logging.getLogger(__name__)


class TriageAgent(BaseAgent[TriageResult]):
    """
    Intelligent Defect Triage Agent.
    Combines rule-based deterministic heuristics with an LLM structured classifier
    and optional retrieval-informed nearest neighbor agreement.
    """

    agent_name = "triage"
    prompt_version = "v1"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        use_retrieval: bool | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._use_retrieval = (
            use_retrieval
            if use_retrieval is not None
            else getattr(settings, "TRIAGE_USE_RETRIEVAL", False)
        )

    def _get_client(self) -> LLMClient | None:
        if self._llm_client is not None:
            return self._llm_client
        provider = getattr(settings, "LLM_PROVIDER", "none") or "none"
        if provider.lower().strip() in ("none", ""):
            return None
        try:
            return get_llm_client()
        except LLMUnavailableError:
            return None

    def _execute(self, input_data: AgentInput, start_t: float) -> AgentResult[TriageResult]:
        # Step 1: Run fast deterministic baseline
        rule_result = evaluate_rule_baseline(input_data)
        warnings: list[str] = list(rule_result.warnings)

        client = self._get_client()

        # If no LLM is configured or available, return rule baseline
        if client is None:
            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
            warnings.append("LLM client not configured; operating in deterministic rule-only mode")
            return AgentResult(
                agent_name=self.agent_name,
                status="ok",
                output=rule_result,
                warnings=warnings,
                error=None,
                duration_ms=elapsed_ms,
                provenance={
                    "method": "rule",
                    "provider": "none",
                    "model": "none",
                    "prompt_version": self.prompt_version,
                    "cache_hit": False,
                },
            )

        # Step 2: Prepare prompt and untrusted input
        registry = get_prompt_registry()
        try:
            system_prompt = registry.get_prompt("triage", self.prompt_version)
        except KeyError:
            system_prompt = "You are a defect triage specialist. Output valid JSON adhering to the schema."

        raw_payload = f"Title: {input_data.title}\nDescription: {input_data.description}\nTrace: {input_data.stack_trace or ''}\nLogs: {input_data.error_logs or ''}"
        safe_wrapped, prep_warnings = sanitize_and_prepare_content(raw_payload)
        warnings.extend(prep_warnings)

        candidates_formatted = "\n".join(f"- {c}" for c in ALL_KNOWN_COMPONENTS[:25])
        user_prompt = (
            f"{safe_wrapped}\n\n"
            f"Candidate Components:\n{candidates_formatted}\n\n"
            f"Rule Baseline Proposal: Severity={rule_result.severity.value}, "
            f"Priority={rule_result.priority.value}, Component={rule_result.component.name}.\n"
            f"Please verify or adjust the classification according to the triage rubric."
        )

        # Step 3: Optional Retrieval context (RAG)
        retrieval_vote: str | None = None
        if self._use_retrieval:
            retrieval_vote = self._fetch_retrieval_prior(input_data)
            if retrieval_vote:
                user_prompt += f"\nHistorical Similar Bug Reference: {retrieval_vote}"

        # Step 4: Call LLM structured generation
        try:
            llm_response = client.generate_structured(
                system_prompt=system_prompt,
                user_content=user_prompt,
                response_model=TriageResult,
                temperature=0.0,
            )
            llm_result = llm_response.data

            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
            combined_warnings = list(set(warnings + llm_result.warnings))

            # Calibrate confidence: agreement between rule and LLM boosts confidence
            conf = llm_result.confidence
            if llm_result.severity == rule_result.severity and llm_result.priority == rule_result.priority:
                conf = min(0.98, conf + 0.05)

            final_result = TriageResult(
                severity=llm_result.severity,
                priority=llm_result.priority,
                component=llm_result.component,
                confidence=round(conf, 2),
                confidence_breakdown=llm_result.confidence_breakdown,
                reasoning=llm_result.reasoning,
                evidence_quotes=llm_result.evidence_quotes,
                signals_used=list(set(rule_result.signals_used + llm_result.signals_used)),
                warnings=combined_warnings,
            )

            return AgentResult(
                agent_name=self.agent_name,
                status="ok",
                output=final_result,
                warnings=combined_warnings,
                error=None,
                duration_ms=elapsed_ms,
                provenance={
                    "method": "hybrid" if llm_response.model != "none" else "llm",
                    "provider": llm_response.provider,
                    "model": llm_response.model,
                    "prompt_version": self.prompt_version,
                    "cache_hit": llm_response.cache_hit,
                },
            )
        except Exception as e:
            logger.warning("LLM triage call failed, gracefully falling back to rule baseline: %s", e)
            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
            warnings.append(f"LLM triage failed ({type(e).__name__}: {e}); fallen back to rule baseline")
            return AgentResult(
                agent_name=self.agent_name,
                status="ok",
                output=rule_result,
                warnings=warnings,
                error=None,
                duration_ms=elapsed_ms,
                provenance={
                    "method": "rule",
                    "provider": "none",
                    "model": "fallback",
                    "prompt_version": self.prompt_version,
                    "cache_hit": False,
                },
            )

    def _fetch_retrieval_prior(self, input_data: AgentInput) -> str | None:
        """Fetches top-1 historical neighbor while enforcing data leakage guard."""
        try:
            from app.rag.retrieval import RetrievalService
            service = RetrievalService()
            query_text = f"{input_data.title} {input_data.description}"
            hits = service.search(query=query_text, top_k=3)
            # Leakage guard: exclude if same bug_id
            for hit in hits:
                if str(hit.get("id")) != str(input_data.bug_id):
                    return (
                        f"Nearest defect #{hit.get('id')} classified as "
                        f"Severity={hit.get('severity', 'Unknown')}, "
                        f"Component={hit.get('component', 'Unknown')}"
                    )
        except Exception as e:
            logger.debug("Retrieval service unavailable for triage prior: %s", e)
        return None
