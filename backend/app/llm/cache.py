from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class LLMCache:
    """Thread-safe on-disk SQLite cache for structured LLM responses."""

    def __init__(self, cache_dir: Path | str = ".llm_cache", enabled: bool = True):
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        self._db_path = self.cache_dir / "llm_responses.db"
        if self.enabled:
            self._init_db()

    def _init_db(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path, timeout=10.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    cache_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
            """)
            conn.commit()

    @staticmethod
    def compute_key(
        provider: str,
        model: str,
        prompt_version: str,
        system_prompt: str,
        user_content: str,
        temperature: float,
    ) -> str:
        payload = f"{provider}:{model}:{prompt_version}:{system_prompt}:{user_content}:{temperature}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        if not self.enabled or not self._db_path.exists():
            return None
        try:
            with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT response_json FROM responses WHERE cache_key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
        except Exception:
            return None
        return None

    def set(self, key: str, data: dict[str, Any], provider: str, model: str) -> None:
        if not self.enabled:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO responses (cache_key, provider, model, response_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (key, provider, model, json.dumps(data), time.time()),
                )
                conn.commit()
        except Exception:
            pass

    def clear(self) -> None:
        if self._db_path.exists():
            try:
                with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                    conn.execute("DELETE FROM responses;")
                    conn.commit()
            except Exception:
                pass
