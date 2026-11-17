from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    diagnosis_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bug_id: Mapped[int] = mapped_column(Integer, ForeignKey("bug_reports.bug_id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), default="heuristic-engine", nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    fix_recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    code_patch: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    similar_defects: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    bug = relationship("BugReport", back_populates="diagnoses")
