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

    # Multi-provider LLM Configuration (Milestone 2)
    LLM_PROVIDER: str = "none"  # "groq" | "gemini" | "ollama" | "fake" | "none"
    LLM_MODEL: str | None = None
    GROQ_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_TIMEOUT_S: float = 30.0
    LLM_MAX_RETRIES: int = 3
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_OUTPUT_TOKENS: int = 2048
    LLM_CACHE_DIR: str = ".llm_cache"
    LLM_CACHE_ENABLED: bool = True
    LLM_REQUESTS_PER_MINUTE: int = 30
    TRIAGE_USE_RETRIEVAL: bool = False
    TRIAGE_TOP_K_NEIGHBOURS: int = 3
    MAX_INPUT_CHARS: int = 12000

    # Orchestration settings (Milestone 2 M2.3)
    ANALYSIS_ON_SUBMIT: bool = True       # Auto-trigger analysis on bug submit
    ANALYSIS_EXECUTION: str = "background"  # "background" | "inline"
    ANALYSIS_TRIAGE_AFTER_LOG: bool = False  # Run triage after log analysis to pass log output
    ANALYSIS_MAX_CONCURRENT: int = 4       # Max concurrent analysis jobs
    PIPELINE_VERSION: str = "2.0.0"        # Bumped with each major orchestration change

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
