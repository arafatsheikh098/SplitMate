"""Empty placeholder routers for milestones that haven't landed yet.

We keep them importable so ``main.create_app`` doesn't fail and so the
test client can still be used to discover every group-scoped route
during M2's route-isolation test.

Once a milestone lands, its real router is registered in
``main._register_milestone_routers``; the stub for that domain becomes
unused but is left in place so older code paths don't break.
"""

from __future__ import annotations

from fastapi import APIRouter

# All M4–M7 routers are now real.  The export stub is still registered
# as a placeholder so the ``_stubs`` import path keeps working for
# future milestones (no path collision today).

export_router = APIRouter()
