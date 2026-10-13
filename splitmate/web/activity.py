"""Activity feed route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from ..db import get_session
from ..i18n import t
from ..models import Group, Member
from ..services.activity import count_activity, list_activity
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


@router.get("/groups/{group_id}/activity")
def activity(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    group, _ = group_member
    activities = list_activity(
        session, group_id=group_id, page=page, page_size=page_size
    )
    total = count_activity(session, group_id=group_id)
    members = session.exec(select(Member).where(Member.group_id == group_id)).all()
    by_id = {m.id: m for m in members}
    body = render(
        "activity.j2",
        {
            "lang": lang,
            "group": group,
            "activities": activities,
            "members_by_id": by_id,
            "page": page,
            "page_size": page_size,
            "total": total,
            "t": t,
        },
    )
    return _html(body, lang=lang, title=t("activity.title", lang=lang))


__all__ = ["router"]
