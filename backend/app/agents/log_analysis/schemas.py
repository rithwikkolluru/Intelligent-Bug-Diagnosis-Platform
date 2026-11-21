from __future__ import annotations


from pydantic import BaseModel, Field


class Frame(BaseModel):
    """Normalized representation of a single call stack execution frame."""

    file: str | None = None
    cls: str | None = Field(default=None, alias="class")
    method: str | None = None
    line: int | None = None
    column: int | None = None
    module_or_package: str | None = None
    is_application_code: bool = True
    raw_frame: str = ""

    model_config = {
        "populate_by_name": True,
        "serialize_by_alias": True,
    }


class ExceptionInfo(BaseModel):
    """Normalized representation of an exception type."""

    fully_qualified: str = ""
    simple_name: str = ""


class FailurePoint(BaseModel):
    """The identified source code location responsible for the failure."""

    file: str | None = None
    cls: str | None = Field(default=None, alias="class")
    method: str | None = None
    line: int | None = None
    column: int | None = None
    module_or_package: str | None = None
    is_application_code: bool = True
    raw_frame: str = ""

    model_config = {
        "populate_by_name": True,
        "serialize_by_alias": True,
    }


class ExceptionChainItem(BaseModel):
    """An exception within a cause-or-suppression chain."""

    type: str = ""
    message: str = ""


class ConfidenceBreakdown(BaseModel):
    """Heuristic scoring components used to calculate overall confidence."""

    exception_type_parsed: bool = False
    error_message_extracted: bool = False
    frames_parsed_count: int = 0
    line_numbers_present: bool = False
    application_frame_found: bool = False
    chain_consistent: bool = False
    parser_fully_consumed: bool = False
    llm_fallback_used: bool = False


class LogAnalysisResult(BaseModel):
    """Structured, versioned outcome of the Log Analysis Agent."""

    schema_version: str = "1.0.0"
    detected_format: str = "unknown"
    exception_type: ExceptionInfo = Field(default_factory=ExceptionInfo)
    error_message: str = ""
    failure_point: FailurePoint | None = None
    code_path: list[Frame] = Field(
        default_factory=list,
        description="Ordered sequence of execution frames from entry point to failure point",
    )
    exception_chain: list[ExceptionChainItem] = Field(default_factory=list)
    root_cause_exception: ExceptionChainItem | None = None
    other_traces_count: int = 0
    primary_trace_selection_reason: str = "default_last_fatal_or_complete"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_breakdown: ConfidenceBreakdown = Field(default_factory=ConfidenceBreakdown)
    evidence: dict[str, str] = Field(
        default_factory=dict,
        description="Quoted verbatim spans from input text supporting extracted facts",
    )
    warnings: list[str] = Field(default_factory=list)
