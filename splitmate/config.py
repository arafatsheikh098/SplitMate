"""Application settings backed by pydantic-settings.

Values come from environment variables (and an optional ``.env`` file).
Refer to ``.env.example`` for the full list.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    env: str = "development"
    secret_key: str = Field(default="change-me-in-production-at-least-32-bytes-random")
    app_name: str = "SplitMate"
    default_language: str = "en"
    session_cookie_name: str = "splitmate_session"
    session_max_age: int = 60 * 60 * 24 * 30  # 30 days

    database_url: str = "sqlite:///./splitmate.db"

    host: str = "0.0.0.0"
    port: int = 8000

    log_level: str = "INFO"

    # Group limits (per SCOPE.md F1)
    max_members_per_group: int = 30
    max_expenses_per_group: int = 5_000

    # Recovery / rate limits (per SCOPE.md F1)
    relink_code_ttl_seconds: int = 60 * 60 * 24
    relink_max_attempts: int = 5
    relink_window_seconds: int = 60 * 15

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def session_cookie_secure(self) -> bool:
        """Secure cookies in production only."""
        return self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()
