from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.bug import BugReport
from app.models.diagnosis import Diagnosis
from app.schemas.bug import BugCreate, BugOut
from app.schemas.diagnosis import DiagnoseRequest, DiagnosisOut, SampleBugOut
from app.services.gemini import diagnose_bug_with_gemini
from app.services.submission import SubmissionError, create_bug_record, validate_bug_payload

router = APIRouter(prefix="/api")

SAMPLE_BUGS = [
    {
        "id": "sample-java-npe",
        "label": "Java: NullPointerException (Auth Service)",
        "title": "NullPointerException in AuthenticationService.authenticate()",
        "description": "User login fails with HTTP 500 error during high traffic periods. When the user object is not found in the cache, the authentication handler crashes trying to access credentials.",
        "stack_trace": (
            "java.lang.NullPointerException: Cannot invoke \"com.example.User.getPasswordHash()\" because \"user\" is null\n"
            "    at com.example.service.AuthenticationService.authenticate(AuthenticationService.java:54)\n"
            "    at com.example.controller.LoginController.doLogin(LoginController.java:31)\n"
            "    at javax.servlet.http.HttpServlet.service(HttpServlet.java:628)\n"
            "    at org.apache.catalina.core.StandardWrapperValve.invoke(StandardWrapperValve.java:238)"
        ),
        "error_logs": "ERROR 2026-11-17 10:14:22 [http-nio-8080-exec-4] AuthenticationService: Failed to authenticate user_id=48291 null pointer encountered",
        "programming_language": "Java",
    },
    {
        "id": "sample-python-keyerror",
        "label": "Python: KeyError in Data Pipeline",
        "title": "KeyError 'customer_id' during stream batch transformation",
        "description": "Worker crash in stream ingestion. When processing webhook events without metadata field, the transformation script raises KeyError and halts processing.",
        "stack_trace": (
            "Traceback (most recent call last):\n"
            "  File \"/app/etl/transformer.py\", line 82, in process_batch\n"
            "    customer_id = record['metadata']['customer_id']\n"
            "KeyError: 'customer_id'"
        ),
        "error_logs": "2026-11-17 10:18:05,214 ERROR transformer.py:85 - Unhandled exception during stream batch processing of record chunk #104",
        "programming_language": "Python",
    },
    {
        "id": "sample-js-typeerror",
        "label": "JavaScript: Cannot read property of undefined",
        "title": "TypeError: Cannot read properties of undefined (reading 'map')",
        "description": "Frontend product listing page crashes on page reload when the API returns an empty response payload or null data object.",
        "stack_trace": (
            "TypeError: Cannot read properties of undefined (reading 'map')\n"
            "    at ProductGrid (ProductGrid.jsx:24:19)\n"
            "    at renderWithHooks (react-dom.development.js:16305:18)\n"
            "    at mountIndeterminateComponent (react-dom.development.js:20074:13)"
        ),
        "error_logs": "Uncaught (in promise) TypeError: Cannot read properties of undefined (reading 'map') at ProductGrid.jsx:24",
        "programming_language": "JavaScript",
    },
    {
        "id": "sample-cpp-segfault",
        "label": "C++: Segmentation fault in Buffer Allocator",
        "title": "SIGSEGV in PacketBuffer::release() double free",
        "description": "Memory corruption and crash during high-throughput packet forwarding when deallocating raw network socket buffers.",
        "stack_trace": (
            "#0  0x00007ffff7a24c37 in __GI_raise (sig=sig@entry=6) at ../sysdeps/unix/sysv/linux/raise.c:51\n"
            "#1  0x00007ffff7a26028 in __GI_abort () at abort.c:79\n"
            "#2  0x0000000000401824 in PacketBuffer::release (this=0x604010) at net/buffer.cpp:112\n"
            "#3  0x0000000000401b92 in NetworkWorker::process (this=0x603f00) at net/worker.cpp:45"
        ),
        "error_logs": "CRITICAL [net.worker] Segmentation fault (core dumped) in PacketBuffer::release()",
        "programming_language": "C/C++",
    },
]


def _format_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        return "\n\n".join(str(x).strip() for x in val if str(x).strip())
    if isinstance(val, dict):
        return json.dumps(val, indent=2)
    return str(val).strip()


def _format_json_field(val: Any) -> str:
    if val is None:
        return "[]"
    if isinstance(val, str):
        return val
    try:
        return json.dumps(val)
    except Exception:
        return "[]"


@router.get("/samples", response_model=list[SampleBugOut])
def get_sample_bugs() -> list[SampleBugOut]:
    """Provide realistic sample bug reports for one-click testing and evaluation."""
    return [SampleBugOut(**s) for s in SAMPLE_BUGS]


@router.post("/bugs/{bug_id}/diagnose", response_model=DiagnosisOut)
async def diagnose_bug(
    bug_id: int,
    request: DiagnoseRequest | None = None,
    x_gemini_api_key: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> DiagnosisOut:
    """Diagnose a bug report using RAG and Gemini AI (or Heuristic Engine fallback)."""
    bug = db.get(BugReport, bug_id)
    if bug is None:
        raise HTTPException(status_code=404, detail={"detail": "Bug not found.", "code": "NOT_FOUND"})

    # Check for existing diagnosis unless forced refresh
    if request and not request.force_refresh:
        existing = db.execute(
            select(Diagnosis).where(Diagnosis.bug_id == bug_id).order_by(Diagnosis.created_at.desc())
        ).scalars().first()
        if existing is not None:
            return DiagnosisOut.model_validate(existing)

    api_key_override = (request.gemini_api_key if request and request.gemini_api_key else None) or x_gemini_api_key
    diag_data = await diagnose_bug_with_gemini(bug, api_key_override=api_key_override)

    diagnosis = Diagnosis(
        bug_id=bug.bug_id,
        status="completed",
        model_used=_format_str(diag_data.get("model_used") or "gemini-flash"),
        root_cause=_format_str(diag_data.get("root_cause") or "Root cause identified."),
        fix_recommendation=_format_str(diag_data.get("fix_recommendation") or "Review recommendations."),
        code_patch=_format_str(diag_data.get("code_patch")) or None,
        verification_steps=_format_json_field(diag_data.get("verification_steps", [])),
        similar_defects=_format_json_field(diag_data.get("similar_defects", [])),
        duplicate_assessment=_format_str(diag_data.get("duplicate_assessment")) or None,
        confidence_score=float(diag_data.get("confidence_score") or 0.85),
    )

    db.add(diagnosis)
    bug.status = "diagnosed"
    db.commit()
    db.refresh(diagnosis)

    return DiagnosisOut.model_validate(diagnosis)


@router.get("/bugs/{bug_id}/diagnosis", response_model=DiagnosisOut)
def get_bug_diagnosis(bug_id: int, db: Session = Depends(get_db)) -> DiagnosisOut:
    """Get the latest diagnosis for a bug report."""
    diagnosis = db.execute(
        select(Diagnosis).where(Diagnosis.bug_id == bug_id).order_by(Diagnosis.created_at.desc())
    ).scalars().first()
    if diagnosis is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Diagnosis not found for this bug report.", "code": "NOT_FOUND"},
        )
    return DiagnosisOut.model_validate(diagnosis)


@router.post("/diagnose", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def submit_and_diagnose(
    payload: BugCreate,
    x_gemini_api_key: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Convenience endpoint: create a bug report and diagnose it immediately."""
    validated = validate_bug_payload(payload.model_dump())
    try:
        bug = create_bug_record(db, validated, source_type="paste")
    except SubmissionError as exc:
        raise HTTPException(status_code=400, detail={"detail": exc.message, "code": exc.code}) from exc

    diag_data = await diagnose_bug_with_gemini(bug, api_key_override=x_gemini_api_key)
    diagnosis = Diagnosis(
        bug_id=bug.bug_id,
        status="completed",
        model_used=_format_str(diag_data.get("model_used") or "gemini-flash"),
        root_cause=_format_str(diag_data.get("root_cause") or "Root cause identified."),
        fix_recommendation=_format_str(diag_data.get("fix_recommendation") or "Review recommendations."),
        code_patch=_format_str(diag_data.get("code_patch")) or None,
        verification_steps=_format_json_field(diag_data.get("verification_steps", [])),
        similar_defects=_format_json_field(diag_data.get("similar_defects", [])),
        duplicate_assessment=_format_str(diag_data.get("duplicate_assessment")) or None,
        confidence_score=float(diag_data.get("confidence_score") or 0.85),
    )
    db.add(diagnosis)
    bug.status = "diagnosed"
    db.commit()
    db.refresh(bug)
    db.refresh(diagnosis)

    return {
        "bug": BugOut.model_validate(bug).model_dump(),
        "diagnosis": DiagnosisOut.model_validate(diagnosis).model_dump(),
    }
