"""Settlements: list, record, delete, restore."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from ..db import get_session
from ..i18n import t
from ..models import Group, Member, Settlement, SettlementMethod
from ..money import format_amount
from ..services.settlements import (
    ServiceError,
    create_settlement,
    list_settlements,
    restore_settlement,
    soft_delete_settlement,
)
from ..templates import render
from .deps import get_lang, require_admin, require_member

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


@router.get("/groups/{group_id}/settle")
def settle_index(
    group_id: int,
    request: Request,
    from_id: str = "",
    to_id: str = "",
    amount: str = "",
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    group, member = group_member
    members = session.exec(
        select(Member).where(
            Member.group_id == group_id, Member.archived == False  # noqa: E712
        )
    ).all()
    settlements = list_settlements(session, group_id=group_id)
    body = render(
        "settlements/index.html.j2",
        {
            "lang": lang,
            "group": group,
            "current_member": member,
            "members": members,
            "settlements": settlements,
            "methods": [m.value for m in SettlementMethod],
            "today": date.today().isoformat(),
            "errors": {},
            "values": {"from_id": from_id, "to_id": to_id, "amount": amount},
            "format_amount": format_amount,
            "t": t,
        },
    )
    return _html(body, lang=lang, title=t("settle.title", lang=lang))


@router.post("/groups/{group_id}/settle")
def settle_create(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    from_id: str = Form(""),
    to_id: str = Form(""),
    amount: str = Form(""),
    method: str = Form(SettlementMethod.OTHER.value),
    date_value: str = Form(""),
    note: str = Form(""),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    group, member = group_member
    data = {
        "from_id": from_id,
        "to_id": to_id,
        "amount": amount,
        "method": method,
        "date": date_value,
        "note": note,
    }
    try:
        create_settlement(
            session, group_id=group_id, creator_id=member.id, data=data
        )
    except ServiceError as exc:
        members = session.exec(
            select(Member).where(
                Member.group_id == group_id, Member.archived == False  # noqa: E712
            )
        ).all()
        settlements = list_settlements(session, group_id=group_id)
        body = render(
            "settlements/index.html.j2",
            {
                "lang": lang,
                "group": group,
                "members": members,
                "settlements": settlements,
                "methods": [m.value for m in SettlementMethod],
                "today": date.today().isoformat(),
                "errors": {"form": str(exc)},
                "values": {
                    "from_id": from_id,
                    "to_id": to_id,
                    "amount": amount,
                    "method": method,
                    "date": date_value,
                    "note": note,
                },
                "format_amount": format_amount,
                "t": t,
            },
        )
        return _html(
            body,
            lang=lang,
            status_code=status.HTTP_400_BAD_REQUEST,
            title=t("settle.title", lang=lang),
        )
    return RedirectResponse(f"/groups/{group_id}/balances", status_code=303)


@router.post("/groups/{group_id}/settlements/{settlement_id}/delete")
def settlement_delete(
    group_id: int,
    settlement_id: int,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> RedirectResponse:
    group, member = group_member
    s = session.get(Settlement, settlement_id)
    if s is None or s.group_id != group_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if s.creator_id != member.id and not member.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    soft_delete_settlement(
        session, group_id=group_id, settlement_id=settlement_id, actor_id=member.id
    )
    return RedirectResponse(f"/groups/{group_id}/settle", status_code=303)


@router.post("/groups/{group_id}/settlements/{settlement_id}/restore")
def settlement_restore(
    group_id: int,
    settlement_id: int,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_admin),
) -> RedirectResponse:
    group, member = group_member
    restore_settlement(
        session, group_id=group_id, settlement_id=settlement_id, actor_id=member.id
    )
    return RedirectResponse(f"/groups/{group_id}/settle", status_code=303)


__all__ = ["router"]
