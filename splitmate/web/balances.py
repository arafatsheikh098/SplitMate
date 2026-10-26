"""Balances + settle-up route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from ..db import get_session
from ..i18n import t
from ..models import Group, Member
from ..money import format_amount
from ..services.balances import group_balances
from ..services.settle import settle_plan
from ..services.settlements import list_settlements
from ..templates import render
from .deps import get_lang, require_member

router = APIRouter()


def _html(content: str, *, lang: str, title: str = "", status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        render(
            "base.html.j2",
            {"lang": lang},
            block_title=title,
            content=content,
        ),
        status_code=status_code,
    )


@router.get("/groups/{group_id}/balances")
def balances(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    group, member = group_member
    balances = group_balances(session, group_id=group_id)
    plan = settle_plan(balances)
    members = session.exec(
        select(Member).where(Member.group_id == group_id)
    ).all()
    by_id = {m.id: m for m in members}
    settlements = list_settlements(session, group_id=group_id)
    body = render(
        "balances.html.j2",
        {
            "lang": lang,
            "group": group,
            "current_member": member,
            "balances": balances,
            "plan": plan,
            "members_by_id": by_id,
            "settlements": settlements,
            "format_amount": format_amount,
            "t": t,
        },
    )
    return _html(body, lang=lang, title=t("balance.title", lang=lang))


__all__ = ["router"]
