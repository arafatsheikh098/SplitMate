"""Shared pytest fixtures.

We isolate tests by giving each a brand-new in-memory SQLite database and
resetting cached engines / translation caches between tests.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Use an in-memory SQLite database by default.  CI sets DATABASE_URL to
# Postgres explicitly.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only")

# Ensure ``splitmate`` is importable when running pytest from the repo root.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_engine() -> Iterator[None]:
    from splitmate import db
    from splitmate.i18n import reload_translations
    from splitmate.templates import reset_for_tests

    # Reset any cached engine and create fresh schema.
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
