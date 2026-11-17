from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./bugs.db"
    MAX_UPLOAD_MB: int = 5
    ALLOWED_EXTENSIONS: list[str] | str = [".txt", ".log", ".md", ".json", ".csv"]
    CORS_ORIGINS: list[str] | str = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://localhost:3000"]
    LOG_LEVEL: str = "INFO"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, value):
        if value is None:
            return ["http://localhost:5173"]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_extensions(cls, value):
        if value is None:
            return [".txt", ".log", ".md", ".json", ".csv"]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = Settings()


def get_settings() -> Settings:
    return settings
