from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.analysis import AgentRun, BugAnalysis
from app.models.bug import BugReport
from app.schemas.bug_context import BugContext

logger = logging.getLogger(__name__)


class AnalysisRepository:
    """Persistence layer for BugAnalysis and AgentRun records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_analysis(self, bug_id: int, pipeline_version: str = "2.0.0") -> BugAnalysis:
        """Create a new analysis record in 'running' state, incrementing attempt counter."""
        last_attempt = (
            self._db.query(BugAnalysis)
            .filter(BugAnalysis.bug_id == bug_id)
            .order_by(BugAnalysis.attempt.desc())
            .first()
        )
        attempt = (last_attempt.attempt + 1) if last_attempt else 1

        analysis = BugAnalysis(
            bug_id=bug_id,
            status="running",
            attempt=attempt,
            pipeline_version=pipeline_version,
        )
        self._db.add(analysis)
        self._db.commit()
        self._db.refresh(analysis)
        return analysis

    def save_context(self, analysis: BugAnalysis, context: BugContext) -> None:
        """Persist the completed BugContext into the analysis record."""
        analysis.status = context.analysis_status
        analysis.context_json = context.model_dump_json()
        analysis.triage_json = json.dumps(context.triage) if context.triage else None
        analysis.log_json = json.dumps(context.log_analysis) if context.log_analysis else None
        analysis.errors_json = json.dumps(context.errors) if context.errors else None
        analysis.updated_at = datetime.now(UTC)
        self._db.commit()

    def save_agent_run(
        self,
        analysis_id: int,
        agent_name: str,
        status: str,
        duration_ms: float,
        error_code: str | None = None,
        provenance: dict | None = None,
    ) -> None:
        run = AgentRun(
            analysis_id=analysis_id,
            agent_name=agent_name,
            status=status,
            error_code=error_code,
            duration_ms=duration_ms,
            provenance_json=json.dumps(provenance or {}),
        )
        self._db.add(run)
        self._db.commit()

    def mark_failed(self, analysis: BugAnalysis, reason: str) -> None:
        analysis.status = "failed"
        analysis.errors_json = json.dumps([{"code": "ANALYSIS_ABORTED", "message": reason}])
        analysis.updated_at = datetime.now(UTC)
        self._db.commit()

    def get_latest(self, bug_id: int) -> BugAnalysis | None:
        return (
            self._db.query(BugAnalysis)
            .filter(BugAnalysis.bug_id == bug_id)
            .order_by(BugAnalysis.attempt.desc())
            .first()
        )

    def get_by_id(self, analysis_id: int) -> BugAnalysis | None:
        return self._db.get(BugAnalysis, analysis_id)

    def is_running(self, bug_id: int) -> bool:
        return (
            self._db.query(BugAnalysis)
            .filter(BugAnalysis.bug_id == bug_id, BugAnalysis.status == "running")
            .count()
        ) > 0

    def recover_stuck(self) -> int:
        """Mark any 'running' analyses that survived a crash as 'failed'. Returns count fixed."""
        stuck = (
            self._db.query(BugAnalysis)
            .filter(BugAnalysis.status == "running")
            .all()
        )
        for analysis in stuck:
            analysis.status = "failed"
            analysis.errors_json = json.dumps([{"code": "ANALYSIS_ABORTED", "message": "Recovered from crash on startup"}])
        if stuck:
            self._db.commit()
        return len(stuck)

    def list_recent(self, limit: int = 20, offset: int = 0) -> list[BugAnalysis]:
        return (
            self._db.query(BugAnalysis)
            .order_by(BugAnalysis.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update_bug_status(self, bug_id: int, status: str) -> None:
        bug = self._db.get(BugReport, bug_id)
        if bug:
            bug.status = status
            self._db.commit()
