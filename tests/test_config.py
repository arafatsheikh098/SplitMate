"""Settings hardening tests (Step 4)."""

from __future__ import annotations

import pytest


def test_production_rejects_placeholder_secret(monkeypatch) -> None:
    """In production, the placeholder SECRET_KEY must be rejected."""
    from splitmate import config

    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv(
        "SECRET_KEY", "change-me-in-production-at-least-32-bytes-random"
    )
    config.get_settings.cache_clear()
    with pytest.raises(Exception) as exc:
        config.get_settings()
    assert "SECRET_KEY" in str(exc.value) or "production" in str(exc.value).lower()


def test_production_rejects_short_secret(monkeypatch) -> None:
    """In production, a too-short SECRET_KEY must be rejected."""
    from splitmate import config

    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "tooshort")
    config.get_settings.cache_clear()
    with pytest.raises(Exception) as exc:
        config.get_settings()
    assert "32" in str(exc.value)


def test_production_accepts_real_secret(monkeypatch) -> None:
    """In production, a 32+ char random secret is accepted."""
    from splitmate import config

    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv(
        "SECRET_KEY",
        "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG",  # 43 chars
    )
    config.get_settings.cache_clear()
    settings = config.get_settings()
    assert settings.is_production
    assert settings.session_cookie_secure


def test_development_allows_placeholder(monkeypatch) -> None:
    """In development, the placeholder SECRET_KEY is accepted."""
    from splitmate import config

    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv(
        "SECRET_KEY", "change-me-in-production-at-least-32-bytes-random"
    )
    config.get_settings.cache_clear()
    settings = config.get_settings()
    assert not settings.is_production
    assert not settings.session_cookie_secure
