"""Migration smoke test (SQLite).  CI repeats this on Postgres."""

from __future__ import annotations

import os
import subprocess
import sys


def test_upgrade_and_downgrade_on_sqlite(tmp_path) -> None:
    db_path = tmp_path / "splitmate.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    # Upgrade
    res = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "running" in res.stdout.lower() or res.returncode == 0
    # Downgrade
    res = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 0
