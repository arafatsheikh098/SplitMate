"""Group, join and member routes (M2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from .. import services
from ..db import get_session
from ..i18n import t
from ..models import Group, Member
from ..money import format_amount
from ..security import (
    login_member,
    logout_member,
)
from ..services import ServiceError, compute_member_balance
from ..templates import render
from .deps import get_lang, require_admin, require_member

router = APIRouter()


def _redirect_with_error(group_id: int, error: str) -> RedirectResponse:
    """Redirect back to the dashboard, surfacing ``error`` as a query string.

    The dashboard template reads ``?error=`` and renders a banner.  We use
    a query string (not a session flash) so the message is single-use and
    never lingers across reloads.
    """
    from urllib.parse import quote

    return RedirectResponse(
        f"/groups/{group_id}?error={quote(error)}", status_code=303
    )


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


@router.get("/groups/new")
def new_group_form(request: Request) -> HTMLResponse:
    lang = get_lang(request)
    body = render(
        "groups/new.html.j2",
        {"lang": lang, "errors": {}, "values": {"name": "", "currency_symbol": "৳", "admin_name": ""}},
    )
    return _html(body, lang=lang, title=t("group.create.title", lang=lang))


@router.post("/groups/new")
def create_group_post(
    request: Request,
    session: Session = Depends(get_session),
    name: Annotated[str, Form()] = "",
    currency_symbol: Annotated[str, Form()] = "৳",
    admin_name: Annotated[str, Form()] = "",
) -> HTMLResponse:
    lang = get_lang(request)
    values = {"name": name, "currency_symbol": currency_symbol, "admin_name": admin_name}
    try:
        group, member, invite = services.create_group(
            session,
            name=name,
            currency_symbol=currency_symbol,
            admin_name=admin_name,
        )
    except ServiceError as e:
        return _html(
            render(
                "groups/new.html.j2",
                {"lang": lang, "errors": {"form": str(e)}, "values": values},
            ),
            lang=lang,
            status_code=status.HTTP_400_BAD_REQUEST,
            title=t("group.create.title", lang=lang),
        )
    # Log admin in immediately.
    login_member(request, group.id, member.id)
    # Render a one-time invite link page.
    body = render(
        "groups/invite_after_create.html.j2",
        {"lang": lang, "group": group, "invite": invite},
    )
    return _html(body, lang=lang, title=t("group.invite.title", lang=lang))


@router.get("/g/{group_id}")
def redirect_to_group(group_id: int, session: Session = Depends(get_session)) -> RedirectResponse:
    """Short URL alias used by the invite page."""
    group = session.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return RedirectResponse(f"/groups/{group.id}", status_code=303)


@router.get("/groups/{group_id}")
def group_dashboard(
    group_id: int,
    request: Request,
    error: str | None = None,
    session: Session = Depends(get_session),
    group_member: tuple = Depends(require_member),
) -> HTMLResponse:
    lang = get_lang(request)
    group, member = group_member
    members = session.exec(select(Member).where(Member.group_id == group_id)).all()
    balances: dict[int, int] = {
        m.id: compute_member_balance(session, group_id=group_id, member_id=m.id)
        for m in members
    }
    body = render(
        "groups/dashboard.html.j2",
        {
            "lang": lang,
            "group": group,
            "members": members,
            "current_member": member,
            "balances": balances,
            "invite_url": None,
            "format_amount": format_amount,
            "t": t,
            "error": error,
        },
    )
    return _html(body, lang=lang, title=group.name)


# ---------------------------------------------------------------------------
# Join via invite link
# ---------------------------------------------------------------------------


@router.get("/join/{token}")
def join_form(token: str, request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    lang = get_lang(request)
    group = services.find_group_by_invite(session, token)
    if group is None:
        return _html(
            render("join/invalid.html.j2", {"lang": lang}),
            lang=lang,
            status_code=status.HTTP_404_NOT_FOUND,
            title=t("group.join.title", lang=lang),
        )
    body = render("join/form.html.j2", {"lang": lang, "group": group, "token": token, "errors": {}})
    return _html(body, lang=lang, title=t("group.join.title", lang=lang))


@router.post("/join/{token}")
def join_post(
    token: str,
    request: Request,
    session: Session = Depends(get_session),
    display_name: Annotated[str, Form()] = "",
) -> HTMLResponse:
    lang = get_lang(request)
    group = services.find_group_by_invite(session, token)
    if group is None:
        return _html(
            render("join/invalid.html.j2", {"lang": lang}),
            lang=lang,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    try:
        member = services.join_group(session, group=group, display_name=display_name)
    except ServiceError as e:
        return _html(
            render(
                "join/form.html.j2",
                {"lang": lang, "group": group, "token": token, "errors": {"name": str(e)}},
            ),
            lang=lang,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    login_member(request, group.id, member.id)
    return RedirectResponse(f"/groups/{group.id}", status_code=303)


# ---------------------------------------------------------------------------
# Re-link (recovery on a new device)
# ---------------------------------------------------------------------------


@router.get("/rejoin/{group_id}/{code}")
def rejoin_form(
    group_id: int,
    code: str,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    lang = get_lang(request)
    group = services.get_group_or_404(session, group_id)
    body = render(
        "rejoin/form.html.j2",
        {"lang": lang, "group": group, "code": code, "errors": {}},
    )
    return _html(body, lang=lang, title=t("auth.invalid_relink", lang=lang))


@router.post("/rejoin/{group_id}/{code}")
def rejoin_post(
    group_id: int,
    code: str,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    lang = get_lang(request)
    group = services.get_group_or_404(session, group_id)
    ip = request.client.host if request.client else "unknown"
    try:
        member = services.consume_relink_code(session, group=group, code=code, ip=ip)
    except ServiceError as e:
        return _html(
            render(
                "rejoin/form.html.j2",
                {"lang": lang, "group": group, "code": code, "errors": {"form": str(e)}},
            ),
            lang=lang,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    login_member(request, group.id, member.id)
    return RedirectResponse(f"/groups/{group.id}", status_code=303)


# ---------------------------------------------------------------------------
# Admin: invite rotation / revoke
# ---------------------------------------------------------------------------


@router.post("/groups/{group_id}/invite/rotate")
def invite_rotate(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_admin),
) -> HTMLResponse:
    lang = get_lang(request)
    group, _ = group_member
    new_token = services.rotate_invite(session, group=group)
    body = render(
        "groups/invite_after_create.html.j2",
        {"lang": lang, "group": group, "invite": new_token, "rotated": True},
    )
    return _html(body, lang=lang, title=t("group.invite.title", lang=lang))


@router.post("/groups/{group_id}/invite/revoke")
def invite_revoke(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_admin),
) -> RedirectResponse:
    group, _ = group_member
    services.revoke_invite(session, group=group)
    return RedirectResponse(f"/groups/{group_id}", status_code=303)


# ---------------------------------------------------------------------------
# Members: add virtual, archive, restore, promote / demote, re-link issue
# ---------------------------------------------------------------------------


@router.post("/groups/{group_id}/members/virtual")
def add_virtual(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
    display_name: Annotated[str, Form()] = "",
    group_member: tuple[Group, Member] = Depends(require_admin),
) -> RedirectResponse:
    group, actor = group_member
    try:
        services.add_virtual_member(
            session, group=group, display_name=display_name, actor_id=actor.id
        )
    except ServiceError as exc:
        return _redirect_with_error(group_id, str(exc))
    return RedirectResponse(f"/groups/{group_id}", status_code=303)


@router.post("/groups/{group_id}/members/{member_id}/archive")
def archive_member(
    group_id: int,
    member_id: int,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_admin),
) -> RedirectResponse:
    group, _ = group_member
    try:
        services.archive_member(session, group=group, member_id=member_id)
    except ServiceError as exc:
        return _redirect_with_error(group_id, str(exc))
    return RedirectResponse(f"/groups/{group_id}", status_code=303)


@router.post("/groups/{group_id}/members/{member_id}/restore")
def restore_member(
    group_id: int,
    member_id: int,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_admin),
) -> RedirectResponse:
    group, _ = group_member
    services.restore_member(session, group=group, member_id=member_id)
    return RedirectResponse(f"/groups/{group_id}", status_code=303)


@router.post("/groups/{group_id}/members/{member_id}/promote")
def promote_member(
    group_id: int,
    member_id: int,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_admin),
) -> RedirectResponse:
    group, _ = group_member
    services.promote(session, group=group, member_id=member_id)
    return RedirectResponse(f"/groups/{group_id}", status_code=303)


@router.post("/groups/{group_id}/members/{member_id}/demote")
def demote_member(
    group_id: int,
    member_id: int,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_admin),
) -> RedirectResponse:
    group, _ = group_member
    try:
        services.demote(session, group=group, member_id=member_id)
    except ServiceError as exc:
        return _redirect_with_error(group_id, str(exc))
    return RedirectResponse(f"/groups/{group_id}", status_code=303)


@router.post("/groups/{group_id}/members/{member_id}/relink")
def issue_relink(
    group_id: int,
    member_id: int,
    request: Request,
    session: Session = Depends(get_session),
    group_member: tuple[Group, Member] = Depends(require_admin),
) -> HTMLResponse:
    lang = get_lang(request)
    group, _ = group_member
    member = services.get_member_or_404(session, group.id, member_id)
    code = services.issue_relink_code(session, group=group, member=member)
    body = render(
        "groups/relink_issued.html.j2",
        {"lang": lang, "group": group, "member": member, "code": code},
    )
    return _html(body, lang=lang, title=t("group.invite.title", lang=lang))


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    logout_member(request)
    return RedirectResponse("/", status_code=303)
