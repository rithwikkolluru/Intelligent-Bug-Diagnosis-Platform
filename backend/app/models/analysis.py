from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class BugAnalysis(Base):
    """Stores the combined agent analysis context for a bug report.

    One row per analysis attempt. The latest attempt is considered canonical.
    Status lifecycle: running -> complete | partial | failed
    """

    __tablename__ = "bug_analyses"

    analysis_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bug_id: Mapped[int] = mapped_column(ForeignKey("bug_reports.bug_id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="running", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(20), nullable=False, default="2.0.0")

    # JSON blobs (stored as TEXT for SQLite portability)
    context_json: Mapped[str | None] = mapped_column(Text, nullable=True)   # Full BugContext as JSON
    triage_json: Mapped[str | None] = mapped_column(Text, nullable=True)    # TriageResult JSON
    log_json: Mapped[str | None] = mapped_column(Text, nullable=True)       # LogAnalysisResult JSON
    errors_json: Mapped[str | None] = mapped_column(Text, nullable=True)    # List of error dicts
    timings_json: Mapped[str | None] = mapped_column(Text, nullable=True)   # Per-node timing dict

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    bug = relationship("BugReport", back_populates="analyses")
    agent_runs = relationship("AgentRun", back_populates="analysis", cascade="all, delete-orphan")


class AgentRun(Base):
    """Per-agent execution record within an analysis attempt."""

    __tablename__ = "agent_runs"

    run_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("bug_analyses.analysis_id", ondelete="CASCADE"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)       # ok | skipped | partial | failed
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_ms: Mapped[float] = mapped_column(nullable=False, default=0.0)
    provenance_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # method, provider, model, etc.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    analysis = relationship("BugAnalysis", back_populates="agent_runs")
