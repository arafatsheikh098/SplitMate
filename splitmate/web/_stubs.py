"""Empty placeholder routers for milestones that haven't landed yet.

We keep them importable so ``main.create_app`` doesn't fail and so the
test client can still be used to discover every group-scoped route
during M2's route-isolation test.
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


expenses_router = APIRouter()


@expenses_router.get("/groups/{group_id}/expenses")
def expenses_index(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    group, member = group_member
    lang = get_lang(request)
    return HTMLResponse(
        render(
            "base.html.j2",
            {"lang": lang},
            block_title="Expenses",
            content="<section class='card'><h1>Expenses (M4)</h1></section>",
        )
    )


@expenses_router.get("/groups/{group_id}/expenses/new")
def expenses_new(
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
            block_title="Add expense",
            content="<section class='card'><h1>Add expense (M4)</h1></section>",
        )
    )


balances_router = APIRouter()


@balances_router.get("/groups/{group_id}/balances")
def balances(
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
            block_title="Balances",
            content="<section class='card'><h1>Balances (M5)</h1></section>",
        )
    )


settlements_router = APIRouter()


@settlements_router.get("/groups/{group_id}/settle")
def settle(
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
            block_title="Settle up",
            content="<section class='card'><h1>Settle up (M5)</h1></section>",
        )
    )


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
