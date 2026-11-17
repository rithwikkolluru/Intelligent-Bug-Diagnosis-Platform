from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.bug import BugReport
from app.schemas.bug import BugCreate, BugListOut, BugOut
from app.services.submission import SubmissionError, create_bug_record, handle_uploaded_file, validate_bug_payload

router = APIRouter(prefix="/api")


def _to_schema(record: BugReport) -> BugOut:
    return BugOut.model_validate(record)


@router.post("/bugs", response_model=BugOut, status_code=status.HTTP_201_CREATED)
def create_bug(payload: BugCreate, db: Session = Depends(get_db)) -> BugOut:
    validated = validate_bug_payload(payload.model_dump())
    try:
        bug = create_bug_record(db, validated, source_type="paste")
    except SubmissionError as exc:
        raise HTTPException(status_code=400, detail={"detail": exc.message, "code": exc.code}) from exc
    return _to_schema(bug)


@router.post("/bugs/upload", response_model=BugOut, status_code=status.HTTP_201_CREATED)
def upload_bug(
    file: UploadFile = File(...),
    title: Annotated[str | None, Form()] = None,
    programming_language: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
) -> BugOut:
    try:
        bug = handle_uploaded_file(db, file, title=title, programming_language=programming_language)
    except SubmissionError as exc:
        raise HTTPException(status_code=400, detail={"detail": exc.message, "code": exc.code}) from exc
    return _to_schema(bug)


@router.get("/bugs/{bug_id}", response_model=BugOut)
def get_bug(bug_id: int, db: Session = Depends(get_db)) -> BugOut:
    bug = db.get(BugReport, bug_id)
    if bug is None:
        raise HTTPException(status_code=404, detail={"detail": "Bug not found.", "code": "NOT_FOUND"})
    return _to_schema(bug)


@router.get("/bugs", response_model=BugListOut)
def list_bugs(
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
) -> BugListOut:
    total = db.query(BugReport).count()
    items = db.execute(select(BugReport).order_by(BugReport.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return BugListOut(items=[_to_schema(item) for item in items], total=total, limit=limit, offset=offset)
