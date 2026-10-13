"""e2e tests run against a separate uvicorn process; do not reuse the
``_isolate_engine`` autouse fixture from the parent conftest.
"""

from __future__ import annotations
