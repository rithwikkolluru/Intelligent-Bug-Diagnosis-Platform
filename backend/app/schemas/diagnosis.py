from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SimilarDefectItem(BaseModel):
    defect_id: str
    title: str
    project: str
    similarity: float = 0.0
    resolution: str = "unknown"
    source_url: str | None = None
    snippet: str | None = None


class DiagnosisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    diagnosis_id: int
    bug_id: int
    status: str
    model_used: str
    root_cause: str
    fix_recommendation: str
    code_patch: str | None = None
    verification_steps: list[str] = Field(default_factory=list)
    similar_defects: list[SimilarDefectItem] = Field(default_factory=list)
    duplicate_assessment: str | None = None
    confidence_score: float = 0.85
    created_at: datetime

    @field_validator("verification_steps", mode="before")
    @classmethod
    def parse_verification_steps(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                return [s.strip() for s in value.split("\n") if s.strip()]
        if isinstance(value, list):
            return [str(x) for x in value]
        return []

    @field_validator("similar_defects", mode="before")
    @classmethod
    def parse_similar_defects(cls, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return []
        if isinstance(value, list):
            return value
        return []


class DiagnoseRequest(BaseModel):
    gemini_api_key: str | None = None
    force_refresh: bool = False


class SampleBugOut(BaseModel):
    id: str
    label: str
    title: str
    description: str
    stack_trace: str
    error_logs: str
    programming_language: str
