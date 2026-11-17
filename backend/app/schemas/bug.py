from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BugCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=3, max_length=300)
    description: str = Field(..., min_length=10)
    stack_trace: str | None = None
    error_logs: str | None = None
    programming_language: str | None = None

    @field_validator("title", "description", "stack_trace", "error_logs", "programming_language")
    @classmethod
    def clean_optional_fields(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        if value and value.strip() == "":
            raise ValueError("title cannot be empty")
        return value.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, value):
        if value and value.strip() == "":
            raise ValueError("description cannot be empty")
        return value.strip()


class BugOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bug_id: int
    title: str
    description: str
    stack_trace: str | None = None
    error_logs: str | None = None
    programming_language: str | None = None
    source_type: str
    original_filename: str | None = None
    status: str
    redaction_count: int
    created_at: datetime


class BugListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[BugOut]
    total: int
    limit: int
    offset: int
