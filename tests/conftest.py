"""Shared pytest fixtures.

We isolate tests by giving each a brand-new file-backed SQLite database
and resetting cached engines / translation caches between tests.  A
file-based URL (in a tmp path) means the schema is shared across all
connections in the pool, unlike ``:memory:``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Default to a file in /tmp so multiple connections see the same data.
# CI sets DATABASE_URL to Postgres explicitly.
os.environ.setdefault("ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only")

# Ensure ``splitmate`` is importable when running pytest from the repo root.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_engine(tmp_path) -> Iterator[None]:
    db_path = tmp_path / "splitmate.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    # Always import the model module so ``SQLModel.metadata`` is populated
    # before ``create_all()`` runs.  Tests that don't import models
    # directly still get a complete schema.
    from splitmate import db, models  # noqa: F401  (registers tables)
    from splitmate.i18n import reload_translations
    from splitmate.templates import reset_for_tests

    # Reset any cached engine and create the schema via SQLAlchemy so
    # each test starts from a clean slate.  Tests that exercise
    # migrations explicitly drop the file first to avoid the duplicate
    # "table already exists" error.
    db.reset_engine_for_tests()
    db.create_all()
    reload_translations()
    reset_for_tests()
    yield
    db.reset_engine_for_tests()


@pytest.fixture
def session():
    from splitmate.db import get_session

    with next(get_session()) as s:
        yield s


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from splitmate.main import create_app

    app = create_app()
    return TestClient(app)
