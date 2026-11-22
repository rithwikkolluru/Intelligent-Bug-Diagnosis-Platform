from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

from app.agents.base import AgentInput
from app.core.config import get_settings
from app.models.bug import BugReport
from app.orchestration.graph import run_analysis
from app.schemas.bug_context import BugContext, BugSnapshot
from app.services.analysis_repo import AnalysisRepository

logger = logging.getLogger(__name__)
settings = get_settings()

# Global semaphore — initialized lazily; controls max concurrent LLM analyses
_SEMAPHORE: asyncio.Semaphore | None = None


def get_semaphore() -> asyncio.Semaphore:
    global _SEMAPHORE
    if _SEMAPHORE is None:
        _SEMAPHORE = asyncio.Semaphore(settings.ANALYSIS_MAX_CONCURRENT)
    return _SEMAPHORE


def build_agent_input(bug: BugReport) -> AgentInput:
    return AgentInput(
        bug_id=bug.bug_id,
        title=bug.title,
        description=bug.description,
        stack_trace=bug.stack_trace,
        error_logs=bug.error_logs,
        programming_language=bug.programming_language,
    )


def build_bug_snapshot(bug: BugReport) -> BugSnapshot:
    return BugSnapshot(
        bug_id=bug.bug_id,
        title=bug.title,
        description=bug.description,
        stack_trace=bug.stack_trace,
        error_logs=bug.error_logs,
        programming_language=bug.programming_language,
        source_type=bug.source_type,
        created_at=bug.created_at.isoformat(),
    )


def run_analysis_sync(db: Session, bug_id: int, force: bool = False) -> BugContext:
    """
    Synchronous entry point for inline test/validation use.
    Bypasses background task machinery.
    """
    repo = AnalysisRepository(db)
    bug = db.get(BugReport, bug_id)
    if bug is None:
        raise ValueError(f"Bug {bug_id} not found")

    if not force and repo.is_running(bug_id):
        raise ValueError(f"Analysis for bug {bug_id} is already running")

    analysis = repo.create_analysis(bug_id, pipeline_version=settings.PIPELINE_VERSION)
    repo.update_bug_status(bug_id, "analyzing")

    try:
        agent_input = build_agent_input(bug)
        snapshot = build_bug_snapshot(bug)
        context = run_analysis(agent_input, snapshot, analysis_id=analysis.analysis_id)
        context.analysis_id = analysis.analysis_id
        repo.save_context(analysis, context)
        repo.update_bug_status(bug_id, f"analysis_{context.analysis_status}")
        return context
    except Exception as exc:
        logger.error("Analysis pipeline failed for bug %d: %s", bug_id, exc)
        repo.mark_failed(analysis, str(exc))
        repo.update_bug_status(bug_id, "analysis_failed")
        raise


async def run_analysis_background(db: Session, bug_id: int) -> None:
    """
    Async background task entry point. Respects semaphore for concurrency limiting.
    DB session is used in a thread-safe manner — called from FastAPI background tasks.
    """
    sem = get_semaphore()
    async with sem:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _execute_analysis, db, bug_id)
        except Exception as exc:
            logger.error("Background analysis failed for bug %d: %s", bug_id, exc)


def _execute_analysis(db: Session, bug_id: int) -> None:
    """Runs in thread executor — does not use async."""
    repo = AnalysisRepository(db)
    bug = db.get(BugReport, bug_id)
    if bug is None:
        logger.warning("Background analysis: bug %d not found", bug_id)
        return

    analysis = repo.create_analysis(bug_id, pipeline_version=settings.PIPELINE_VERSION)
    repo.update_bug_status(bug_id, "analyzing")

    try:
        agent_input = build_agent_input(bug)
        snapshot = build_bug_snapshot(bug)
        context = run_analysis(agent_input, snapshot, analysis_id=analysis.analysis_id)
        context.analysis_id = analysis.analysis_id
        repo.save_context(analysis, context)
        repo.update_bug_status(bug_id, f"analysis_{context.analysis_status}")
        logger.info("Analysis complete for bug %d: status=%s", bug_id, context.analysis_status)
    except Exception as exc:
        logger.error("Analysis pipeline error for bug %d: %s", bug_id, exc)
        repo.mark_failed(analysis, str(exc))
        repo.update_bug_status(bug_id, "analysis_failed")
