from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.services.analysis_repo import AnalysisRepository
from app.services.analysis_service import run_analysis_background, run_analysis_sync

router = APIRouter(prefix="/api")
settings = get_settings()


def _context_from_db(analysis) -> dict[str, Any]:
    if analysis.context_json:
        return json.loads(analysis.context_json)
    return {
        "analysis_id": analysis.analysis_id,
        "bug_id": analysis.bug_id,
        "analysis_status": analysis.status,
        "attempt": analysis.attempt,
        "created_at": analysis.created_at.isoformat(),
        "schema_version": "2.0",
    }


@router.get(
    "/bugs/{bug_id}/analysis",
    summary="Get analysis result for a bug",
    response_model=None,
    status_code=200,
)
def get_analysis(bug_id: int, db: Session = Depends(get_db)):
    repo = AnalysisRepository(db)
    analysis = repo.get_latest(bug_id)
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "No analysis found for this bug.", "code": "ANALYSIS_NOT_FOUND"},
        )
    if analysis.status == "running":
        return {"analysis_status": "running", "analysis_id": analysis.analysis_id, "bug_id": bug_id}
    return _context_from_db(analysis)


@router.post(
    "/bugs/{bug_id}/analyze",
    summary="Trigger or re-run analysis for a bug",
    status_code=202,
)
def trigger_analysis(
    bug_id: int,
    background_tasks: BackgroundTasks,
    force: bool = False,
    db: Session = Depends(get_db),
):
    repo = AnalysisRepository(db)
    if repo.is_running(bug_id) and not force:
        raise HTTPException(
            status_code=409,
            detail={"detail": "Analysis is already running for this bug.", "code": "ANALYSIS_IN_PROGRESS"},
        )

    if settings.ANALYSIS_EXECUTION == "inline":
        try:
            context = run_analysis_sync(db, bug_id, force=force)
            return context.model_dump(mode="json")
        except ValueError as e:
            raise HTTPException(status_code=404, detail={"detail": str(e), "code": "NOT_FOUND"})
    else:
        background_tasks.add_task(run_analysis_background, db, bug_id)
        return {"detail": "Analysis triggered.", "bug_id": bug_id, "status": "queued"}


@router.get("/analyses", summary="List recent analyses (summary)")
def list_analyses(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    repo = AnalysisRepository(db)
    items = repo.list_recent(limit=limit, offset=offset)
    return {
        "items": [
            {
                "analysis_id": a.analysis_id,
                "bug_id": a.bug_id,
                "status": a.status,
                "attempt": a.attempt,
                "pipeline_version": a.pipeline_version,
                "created_at": a.created_at.isoformat(),
            }
            for a in items
        ],
        "count": len(items),
        "limit": limit,
        "offset": offset,
    }


@router.get("/analysis/config", summary="Active analysis pipeline configuration (no secrets)")
def analysis_config():
    return {
        "provider": settings.LLM_PROVIDER,
        "model": settings.LLM_MODEL,
        "analysis_on_submit": settings.ANALYSIS_ON_SUBMIT,
        "analysis_execution": settings.ANALYSIS_EXECUTION,
        "triage_after_log": settings.ANALYSIS_TRIAGE_AFTER_LOG,
        "triage_use_retrieval": settings.TRIAGE_USE_RETRIEVAL,
        "max_concurrent": settings.ANALYSIS_MAX_CONCURRENT,
        "pipeline_version": settings.PIPELINE_VERSION,
    }
