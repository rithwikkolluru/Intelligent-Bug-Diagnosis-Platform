from __future__ import annotations

import logging
import time
from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.base import AgentInput
from app.agents.log_analysis.agent import LogAnalysisAgent
from app.agents.triage.agent import TriageAgent
from app.core.config import get_settings
from app.schemas.bug_context import AgentRunRecord, BugContext, BugSnapshot, build_derived_facts

logger = logging.getLogger(__name__)

settings = get_settings()


def _last(a: Any, b: Any) -> Any:
    """Reducer: last-write-wins for optional dict fields written by exactly one parallel branch."""
    return b if b is not None else a


# ---------------------------------------------------------------------------
# Graph State — Annotated reducers for fields touched by parallel branches
# ---------------------------------------------------------------------------
class AnalysisState(TypedDict):
    agent_input: AgentInput                              # written once by validate_input
    bug_snapshot: dict[str, Any]                        # written once at graph entry
    triage_result: Annotated[dict[str, Any] | None, _last]   # written by triage branch
    triage_run: Annotated[dict[str, Any] | None, _last]       # written by triage branch
    log_result: Annotated[dict[str, Any] | None, _last]       # written by log branch
    log_run: Annotated[dict[str, Any] | None, _last]          # written by log branch
    errors: Annotated[list[dict[str, str]], add]        # merged from both branches
    warnings: Annotated[list[str], add]                 # merged from both branches


# ---------------------------------------------------------------------------
# Node: validate_input
# ---------------------------------------------------------------------------
def validate_input_node(state: AnalysisState) -> dict:
    inp = state["agent_input"]
    errors: list[dict[str, str]] = []
    warnings: list[str] = []

    # Reject completely empty input
    if not inp.title.strip() and not inp.description.strip() and not inp.stack_trace and not inp.error_logs:
        errors.append({"code": "INVALID_INPUT", "message": "Bug report contains no meaningful content."})

    return {"errors": errors, "warnings": warnings}


# ---------------------------------------------------------------------------
# Node: triage_node
# ---------------------------------------------------------------------------
def triage_node(state: AnalysisState) -> dict:
    if any(e["code"] == "INVALID_INPUT" for e in state.get("errors", [])):
        return {
            "triage_result": None,
            "triage_run": {"agent_name": "triage", "status": "skipped", "error_code": "INVALID_INPUT", "duration_ms": 0, "provenance": {}},
            "warnings": [],
            "errors": [],
        }

    inp = state["agent_input"]
    agent = TriageAgent()
    t0 = time.perf_counter()

    try:
        result = agent.run(inp)
        triage_dict = result.output.model_dump(mode="json") if result.output else None
        run = {
            "agent_name": "triage",
            "status": result.status,
            "error_code": result.error.get("code") if result.error else None,
            "duration_ms": result.duration_ms,
            "provenance": result.provenance,
        }
        return {"triage_result": triage_dict, "triage_run": run, "warnings": result.warnings, "errors": []}
    except Exception as exc:
        logger.warning("Triage node raised unexpectedly: %s", exc)
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "triage_result": None,
            "triage_run": {"agent_name": "triage", "status": "failed", "error_code": "AGENT_FAILED", "duration_ms": duration_ms, "provenance": {}},
            "warnings": [],
            "errors": [],
        }


# ---------------------------------------------------------------------------
# Node: log_analysis_node
# ---------------------------------------------------------------------------
def log_analysis_node(state: AnalysisState) -> dict:
    if any(e["code"] == "INVALID_INPUT" for e in state.get("errors", [])):
        return {
            "log_result": None,
            "log_run": {"agent_name": "log_analysis", "status": "skipped", "error_code": "INVALID_INPUT", "duration_ms": 0, "provenance": {}},
            "warnings": [],
            "errors": [],
        }

    inp = state["agent_input"]

    # If no log content at all, return a documented 'skipped' result — this is NOT an error
    if not inp.stack_trace and not inp.error_logs:
        return {
            "log_result": None,
            "log_run": {
                "agent_name": "log_analysis",
                "status": "skipped",
                "error_code": "NO_LOG_CONTENT",
                "duration_ms": 0,
                "provenance": {"method": "rule"},
            },
            "warnings": [],
            "errors": [],
        }

    agent = LogAnalysisAgent()
    t0 = time.perf_counter()

    try:
        result = agent.run(inp)
        log_dict = result.output.model_dump(mode="json") if result.output else None
        run = {
            "agent_name": "log_analysis",
            "status": result.status,
            "error_code": result.error.get("code") if result.error else None,
            "duration_ms": result.duration_ms,
            "provenance": result.provenance,
        }
        warnings = list(state.get("warnings", [])) + result.warnings
        return {**state, "log_result": log_dict, "log_run": run, "warnings": warnings}
    except Exception as exc:
        logger.warning("Log analysis node raised unexpectedly: %s", exc)
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            **state,
            "log_result": None,
            "log_run": {"agent_name": "log_analysis", "status": "failed", "error_code": "AGENT_FAILED", "duration_ms": duration_ms, "provenance": {}},
        }


# ---------------------------------------------------------------------------
# Node: triage_after_log_node (ANALYSIS_TRIAGE_AFTER_LOG=True mode)
# ---------------------------------------------------------------------------
def triage_after_log_node(state: AnalysisState) -> AnalysisState:
    """Triage that receives log analysis output as optional context."""
    if any(e["code"] == "INVALID_INPUT" for e in state.get("errors", [])):
        return {**state, "triage_result": None, "triage_run": {"status": "skipped", "error_code": "INVALID_INPUT", "duration_ms": 0}}

    inp = state["agent_input"]
    log_result = state.get("log_result")

    # Enrich input description with log findings if available
    enriched_inp = inp
    if log_result:
        exc_type = log_result.get("exception_type", {}) or {}
        exc_name = exc_type.get("simple_name") or exc_type.get("fully_qualified") or ""
        fp = log_result.get("failure_point") or {}
        fp_summary = f"{fp.get('file','?')}:{fp.get('line','?')} in {fp.get('method','?')}" if fp else ""
        log_hint = f"\n[Log Analysis Findings: Exception={exc_name}, Failure Point={fp_summary}]"
        enriched_inp = AgentInput(
            bug_id=inp.bug_id,
            title=inp.title,
            description=(inp.description or "") + log_hint,
            stack_trace=inp.stack_trace,
            error_logs=inp.error_logs,
            programming_language=inp.programming_language,
        )

    agent = TriageAgent()
    t0 = time.perf_counter()
    try:
        result = agent.run(enriched_inp)
        triage_dict = result.output.model_dump(mode="json") if result.output else None
        run = {
            "agent_name": "triage",
            "status": result.status,
            "error_code": result.error.get("code") if result.error else None,
            "duration_ms": result.duration_ms,
            "provenance": {**result.provenance, "log_enriched": True},
        }
        warnings = list(state.get("warnings", [])) + result.warnings
        return {**state, "triage_result": triage_dict, "triage_run": run, "warnings": warnings}
    except Exception as exc:
        logger.warning("Triage-after-log node raised unexpectedly: %s", exc)
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            **state,
            "triage_result": None,
            "triage_run": {"agent_name": "triage", "status": "failed", "error_code": "AGENT_FAILED", "duration_ms": duration_ms, "provenance": {}},
        }


# ---------------------------------------------------------------------------
# Node: merge_context_node
# ---------------------------------------------------------------------------
def merge_context_node(state: AnalysisState) -> AnalysisState:
    """Combine triage + log results into final BugContext."""
    triage_run = state.get("triage_run") or {}
    log_run = state.get("log_run") or {}

    triage_ok = triage_run.get("status") in ("ok", "partial")

    errors = list(state.get("errors", []))
    if not triage_ok and triage_run.get("status") == "failed":
        errors.append({"code": "AGENT_FAILED", "message": "Triage agent failed; rule baseline may be unavailable."})
    if log_run.get("status") == "failed":
        errors.append({"code": "AGENT_FAILED", "message": "Log analysis agent failed."})

    return {**state, "errors": errors}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------
def _build_graph(triage_after_log: bool = False) -> Any:
    graph = StateGraph(AnalysisState)
    graph.add_node("validate_input", validate_input_node)
    graph.add_node("log_analysis", log_analysis_node)
    graph.add_node("triage", triage_node if not triage_after_log else triage_after_log_node)
    graph.add_node("merge_context", merge_context_node)

    graph.add_edge(START, "validate_input")

    if triage_after_log:
        # Sequential: log -> triage -> merge
        graph.add_edge("validate_input", "log_analysis")
        graph.add_edge("log_analysis", "triage")
        graph.add_edge("triage", "merge_context")
    else:
        # Parallel: validate -> (log | triage) -> merge
        graph.add_edge("validate_input", "log_analysis")
        graph.add_edge("validate_input", "triage")
        graph.add_edge("log_analysis", "merge_context")
        graph.add_edge("triage", "merge_context")

    graph.add_edge("merge_context", END)
    return graph.compile()


# Compile graphs once at module load
_PARALLEL_GRAPH = _build_graph(triage_after_log=False)
_SEQUENTIAL_GRAPH = _build_graph(triage_after_log=True)


def run_analysis(
    bug_input: AgentInput,
    bug_snapshot: BugSnapshot,
    analysis_id: int | None = None,
    triage_after_log: bool | None = None,
) -> BugContext:
    """
    Entry point for the analysis pipeline.
    Returns a fully populated BugContext. Never raises.
    """
    use_sequential = triage_after_log if triage_after_log is not None else settings.ANALYSIS_TRIAGE_AFTER_LOG
    graph = _SEQUENTIAL_GRAPH if use_sequential else _PARALLEL_GRAPH

    initial_state: AnalysisState = {
        "agent_input": bug_input,
        "bug_snapshot": bug_snapshot.model_dump(mode="json"),
        "triage_result": None,
        "triage_run": None,
        "log_result": None,
        "log_run": None,
        "errors": [],
        "warnings": [],
    }

    try:
        final_state = graph.invoke(initial_state)
    except Exception as exc:
        logger.error("Graph invocation failed completely: %s", exc)
        return BugContext(
            analysis_id=analysis_id,
            bug=bug_snapshot,
            analysis_status="failed",
            errors=[{"code": "ANALYSIS_ABORTED", "message": str(exc)}],
            warnings=[],
            pipeline_version=settings.PIPELINE_VERSION,
        )

    # Build derived facts from live objects if available, else skip
    triage_obj = None
    log_obj = None

    # We get serialized dicts back from the graph; re-hydrate enough for derived facts
    triage_dict = final_state.get("triage_result")
    log_dict = final_state.get("log_result")

    class _SimpleObj:
        pass

    if triage_dict:
        triage_obj = _SimpleObj()
        for k, v in triage_dict.items():
            setattr(triage_obj, k, v)
        # Handle nested enums
        sev = triage_dict.get("severity")
        if sev:
            class _Enum:
                value = sev
            triage_obj.severity = _Enum()
        prio = triage_dict.get("priority")
        if prio:
            class _Enum:
                value = prio
            triage_obj.priority = _Enum()
        comp = triage_dict.get("component")
        if comp:
            c = _SimpleObj()
            c.name = comp.get("name")
            triage_obj.component = c

    if log_dict:
        log_obj = _SimpleObj()
        for k, v in log_dict.items():
            setattr(log_obj, k, v)
        exc_type = log_dict.get("exception_type") or {}
        et = _SimpleObj()
        et.simple_name = exc_type.get("simple_name")
        et.fully_qualified = exc_type.get("fully_qualified")
        log_obj.exception_type = et
        fp_dict = log_dict.get("failure_point")
        if fp_dict:
            fp = _SimpleObj()
            for k, v in fp_dict.items():
                setattr(fp, k, v)
            log_obj.failure_point = fp
        else:
            log_obj.failure_point = None

    derived = build_derived_facts(triage_obj, log_obj, bug_snapshot.programming_language)

    triage_run = final_state.get("triage_run") or {}
    log_run = final_state.get("log_run") or {}

    agent_runs = []
    for run_dict in [triage_run, log_run]:
        if run_dict:
            agent_runs.append(AgentRunRecord(
                agent_name=run_dict.get("agent_name", "unknown"),
                status=run_dict.get("status", "failed"),
                error_code=run_dict.get("error_code"),
                duration_ms=run_dict.get("duration_ms", 0.0),
                provenance=run_dict.get("provenance") or {},
            ))

    triage_ok = triage_run.get("status") in ("ok", "partial")
    log_ok = log_run.get("status") in ("ok", "partial", "skipped")
    if triage_ok and log_ok:
        analysis_status = "complete"
    elif triage_ok or log_ok:
        analysis_status = "partial"
    else:
        analysis_status = "failed"

    errors = final_state.get("errors", [])
    if any(e["code"] == "INVALID_INPUT" for e in errors):
        analysis_status = "failed"

    return BugContext(
        schema_version="2.0",
        pipeline_version=settings.PIPELINE_VERSION,
        analysis_id=analysis_id,
        bug=bug_snapshot,
        triage=triage_dict,
        log_analysis=log_dict,
        derived=derived,
        analysis_status=analysis_status,
        agent_runs=agent_runs,
        warnings=final_state.get("warnings", []),
        errors=errors,
    )
