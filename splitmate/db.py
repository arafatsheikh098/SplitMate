"""Database engine, session, and metadata.

A single SQLModel ``Engine`` per process.  The same engine is used for both
Postgres and SQLite — SQLAlchemy abstracts the difference and Alembic handles
schema migrations.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use."""
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        connect_args: dict[str, Any] = {}
        if url.startswith("sqlite"):
            # SQLite needs a per-thread connection when used by FastAPI's
            # threadpool, and FK enforcement to be on.
            connect_args = {"check_same_thread": False}
        _engine = create_engine(
            url,
            echo=False,
            future=True,
            connect_args=connect_args,
        )
        # For SQLite, enable foreign keys.
        if url.startswith("sqlite"):
            from sqlalchemy import event

            @event.listens_for(_engine, "connect")
            def _enable_fk(dbapi_conn, _):  # pragma: no cover - dialect-level glue
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()

    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yield a session and ensure it is closed."""
    with Session(get_engine()) as session:
        yield session


def create_all() -> None:
    """Create all tables directly. Used in tests and the first-run bootstrap."""
    SQLModel.metadata.create_all(get_engine())


def reset_engine_for_tests() -> None:
    """Drop the cached engine (used between tests)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
