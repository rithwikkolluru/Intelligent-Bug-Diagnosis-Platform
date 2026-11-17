from __future__ import annotations

import os

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    has_key = bool(settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY"))
    return {
        "status": "ok",
        "version": "0.1.0",
        "gemini_configured": has_key,
        "gemini_model": settings.GEMINI_MODEL,
        "database": "connected",
    }
