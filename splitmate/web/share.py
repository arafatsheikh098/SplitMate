"""Share / summary route (M7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ..db import get_session
from ..i18n import t
from ..models import Group, Member
from ..services.share import build_summary, render_summary
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


@router.get("/groups/{group_id}/summary")
def summary(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    group, _ = group_member
    sections = build_summary(session, group_id=group_id, lang=lang)
    summary_text = render_summary(sections)
    body = render(
        "share/summary.html.j2",
        {
            "lang": lang,
            "group": group,
            "summary_text": summary_text,
            "t": t,
        },
    )
    return _html(body, lang=lang, title=t("share.title", lang=lang))


@router.get("/groups/{group_id}/summary.txt")
def summary_text(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    group, _ = group_member
    sections = build_summary(session, group_id=group_id, lang=lang)
    text = render_summary(sections)
    return HTMLResponse(
        content=text,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{_safe_filename(group.name)}-summary.txt"'
            )
        },
    )


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)[:40] or "group"


__all__ = ["router"]
