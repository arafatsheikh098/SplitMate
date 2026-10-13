"""Migration smoke test (SQLite).  CI repeats this on Postgres."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_upgrade_and_downgrade_on_sqlite(tmp_path) -> None:
    db_path = tmp_path / "splitmate.db"
    # Make sure the file does not exist (autouse fixture created tables).
    if db_path.exists():
        db_path.unlink()
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    repo_root = Path(__file__).resolve().parent.parent
    # Upgrade
    res = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=env,
        cwd=repo_root,
    )
    with open("/tmp/alembic.log", "w") as fh:
        fh.write(f"rc={res.returncode}\nstdout={res.stdout}\nstderr={res.stderr}\n")
    assert res.returncode == 0, res.stderr
    # Downgrade
    res = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        capture_output=True,
        text=True,
        env=env,
        cwd=repo_root,
    )
    assert res.returncode == 0, (res.stdout, res.stderr)
