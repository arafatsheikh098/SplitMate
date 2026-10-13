"""Empty placeholder routers for milestones that haven't landed yet.

We keep them importable so ``main.create_app`` doesn't fail and so the
test client can still be used to discover every group-scoped route
during M2's route-isolation test.

Once a milestone lands, its real router is registered in
``main._register_milestone_routers``; the stub for that domain becomes
unused but is left in place so older code paths don't break.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ..db import get_session
from ..i18n import t
from ..models import Group, Member
from ..templates import render
from .deps import get_lang, require_member


def _stub_html(request: Request, group: Group, member: Member, label: str) -> HTMLResponse:
    lang = get_lang(request)
    body = render(
        "groups/dashboard.html.j2",
        {
            "lang": lang,
            "group": group,
            "members": [member],
            "current_member": member,
            "balances": {member.id: 0},
            "invite_url": None,
            "t": t,
        },
    )
    return HTMLResponse(body)


# Milestones M6 / M7 still have no real implementation; their stubs
# are mounted.  M4 (expenses) and M5 (balances + settlements) are
# implemented, so their stubs are intentionally not registered.

activity_router = APIRouter()


@activity_router.get("/groups/{group_id}/activity")
def activity(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    return HTMLResponse(
        render(
            "base.html.j2",
            {"lang": lang},
            block_title="Activity",
            content="<section class='card'><h1>Activity (M6)</h1></section>",
        )
    )


share_router = APIRouter()


@share_router.get("/groups/{group_id}/summary")
def summary(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    return HTMLResponse(
        render(
            "base.html.j2",
            {"lang": lang},
            block_title="Summary",
            content="<section class='card'><h1>Summary (M7)</h1></section>",
        )
    )
